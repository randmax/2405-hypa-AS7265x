import csv
import os
from pathlib import Path
import queue
import tempfile
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
            received = []
            deadline = time.monotonic() + 2
            while len([e for e in received if e[0] == "sample"]) < 2 and time.monotonic() < deadline:
                received.append(events.get(timeout=2))
            worker.stop_event.set()
            worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertTrue(fake.closed)
        self.assertEqual(len([e for e in received if e[0] == "sample"]), 2)
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
            kind, values = events.get(timeout=2)
            self.assertEqual(kind, "sample")
            np.testing.assert_array_equal(values, np.arange(18))
        finally:
            worker.stop_event.set()
            worker.join(1)
            os.close(master)
            os.close(slave)
        self.assertFalse(worker.is_alive())
