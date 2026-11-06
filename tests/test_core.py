import csv
import os
from pathlib import Path
import queue
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np
from spectral_core import Acquisition, SpectrumBuffer, parse_sample


class CoreTests(unittest.TestCase):
    def test_parser_and_trailing_comma(self):
        expected = np.arange(18, dtype=float)
        np.testing.assert_array_equal(parse_sample(",".join(map(str, expected)) + ",\r\n"), expected)

    def test_rejects_headers_wrong_count_and_non_finite(self):
        for line in ("Example", "1,2", ",".join(["NaN"] * 18), ",".join(["inf"] * 18),
                     ",".join(["1e200"] * 18), ",".join(["bad"] * 18)):
            with self.subTest(line=line):
                self.assertIsNone(parse_sample(line))

    def test_bounded_rolling_mean_resize_and_order(self):
        buffer = SpectrumBuffer(3)
        for value in range(20):
            buffer.append(np.full(18, value, dtype=float))
        self.assertEqual(len(buffer), 3)
        np.testing.assert_allclose(buffer.mean(), 18)
        np.testing.assert_array_equal(buffer.recent(2)[:, 0], [18, 19])
        buffer.resize(2)
        np.testing.assert_allclose(buffer.mean(), 18.5)
        buffer.resize(4)
        buffer.append(np.full(18, 20.0))
        np.testing.assert_allclose(buffer.mean(), 19)

    def test_live_snapshot_and_optional_average_are_independent_of_history(self):
        buffer = SpectrumBuffer(100)
        for _ in range(99):
            buffer.append(np.full(18, 1000.0))
        latest = np.arange(18, dtype=float)
        buffer.append(latest)
        live = buffer.snapshot(rows=3)
        np.testing.assert_array_equal(live.values, latest)
        self.assertEqual(live.count, 100)
        self.assertEqual(live.received, 100)
        np.testing.assert_allclose(buffer.snapshot(average=2).values, (1000 + latest) / 2)
        np.testing.assert_allclose(buffer.snapshot(average=100).values, buffer.mean())
        np.testing.assert_array_equal(live.history[-1], latest)
        self.assertGreater(live.received_at, 0)

    def test_serial_burst_cannot_be_blocked_by_a_full_gui_queue(self):
        samples = 5000
        payload = (b"Example header\n" * 2000 + b"".join(
            (",".join(str(i + channel) for channel in range(18)) + "\n").encode()
            for i in range(samples)))
        drained = threading.Event()

        class BurstSerial:
            def __init__(self):
                self.offset = 0

            @property
            def in_waiting(self):
                return len(payload) - self.offset

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self, count):
                block = payload[self.offset:self.offset + count]
                self.offset += len(block)
                if not block:
                    drained.set()
                    time.sleep(0.005)
                return block

        events = queue.Queue(maxsize=1)
        events.put(("message", "GUI not processing events"))
        buffer = SpectrumBuffer(64)
        worker = Acquisition(events, "test", 115200, buffer=buffer)
        with patch("spectral_core.serial.serial_for_url", return_value=BurstSerial()):
            worker.start()
            try:
                self.assertTrue(drained.wait(5), "Serial input backed up behind the GUI")
                snapshot = buffer.snapshot(rows=64)
                self.assertEqual(snapshot.received, samples)
                self.assertEqual(snapshot.count, 64)
                np.testing.assert_array_equal(snapshot.values, np.arange(18) + samples - 1)
                np.testing.assert_array_equal(snapshot.history[:, 0], np.arange(samples - 64, samples))
                self.assertGreater(worker.suppressed_messages, 0)
                self.assertLessEqual(events.qsize(), 1)
            finally:
                worker.stop_event.set()
                worker.join(1)
        self.assertFalse(worker.is_alive())

    def test_capacity_is_validated(self):
        for size in (0, -1, 10001):
            with self.assertRaises(ValueError):
                SpectrumBuffer(size)

    def test_original_values_export_after_stop(self):
        buffer = SpectrumBuffer(2)
        values = np.arange(18, dtype=float) / 4
        buffer.append(values)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "meres.csv"
            buffer.save_csv(path)
            with path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.reader(stream))
        self.assertEqual(rows[0][0], "410nm")
        self.assertEqual(rows[0][-1], "940nm")
        np.testing.assert_array_equal(np.asarray(rows[1], dtype=float), values)

    def test_full_event_queue_can_be_cancelled(self):
        events = queue.Queue(maxsize=1)
        worker = Acquisition(events, "", 115200, demo=True)
        worker.start()
        time.sleep(0.05)
        worker.stop_event.set()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertLessEqual(events.qsize(), 1)

    def test_partial_lines_overlong_line_recovery_and_port_close(self):
        sample = ",".join(str(v) for v in range(18)).encode() + b",\r\n"
        blocks = [b"Example header\n", sample[:7], sample[7:], b"X" * 4096,
                  b"XXXX\n", sample]

        class FakeSerial:
            closed = False
            in_waiting = 4096

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.closed = True

            def read(self, count):
                if blocks:
                    return blocks.pop(0)
                time.sleep(0.01)
                return b""

        fake = FakeSerial()
        events = queue.Queue(maxsize=512)
        worker = Acquisition(events, "test", 115200)
        with patch("spectral_core.serial.serial_for_url", return_value=fake):
            worker.start()
            deadline = time.monotonic() + 2
            while worker.buffer.received < 2 and time.monotonic() < deadline:
                time.sleep(0.005)
            worker.stop_event.set()
            worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertTrue(fake.closed)
        received = list(events.queue)
        self.assertEqual(worker.buffer.received, 2)
        np.testing.assert_array_equal(worker.buffer.snapshot().values, np.arange(18))
        self.assertTrue(any("4096" in str(e[1]) for e in received))

    @unittest.skipUnless(os.name == "posix", "Linux PTY test")
    def test_real_linux_pty_serial_input(self):
        import pty
        master, slave = pty.openpty()
        events = queue.Queue(maxsize=512)
        worker = Acquisition(events, os.ttyname(slave), 115200)
        try:
            worker.start()
            self.assertEqual(events.get(timeout=2)[0], "ready")
            sample = ",".join(map(str, range(18))).encode() + b"\n"
            os.write(master, sample[:8])
            os.write(master, sample[8:])
            deadline = time.monotonic() + 2
            while not worker.buffer.received and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertEqual(worker.buffer.received, 1)
            np.testing.assert_array_equal(worker.buffer.snapshot().values, np.arange(18))
        finally:
            worker.stop_event.set()
            worker.join(1)
            os.close(master)
            os.close(slave)
        self.assertFalse(worker.is_alive())
