"""Bounded data storage and serial I/O; this module never touches Tk widgets."""

from collections import deque
from dataclasses import dataclass
import csv
from itertools import islice
import math
from pathlib import Path
import queue
import threading
import time

import numpy as np
import serial

WAVELENGTHS = (410, 435, 460, 485, 510, 535, 560, 585, 610,
               645, 680, 705, 730, 760, 810, 860, 900, 940)
MAX_SAMPLES = 10000
MAX_LINE_BYTES = 4096
CONTROL_QUEUE_SIZE = 64


@dataclass(frozen=True)
class SpectrumSnapshot:
    values: np.ndarray
    history: np.ndarray
    count: int
    capacity: int
    received: int
    received_at: float


def parse_sample(line):
    """Accept 18 finite comma-separated numbers, with an optional trailing comma."""
    parts = line.strip().removesuffix(",").split(",")
    if len(parts) != len(WAVELENGTHS):
        return None
    try:
        values = [float(part) for part in parts]
    except ValueError:
        return None
    if not all(math.isfinite(v) and abs(v) <= 1e100 for v in values):
        return None
    return np.asarray(values, dtype=float)


class SpectrumBuffer:
    def __init__(self, capacity=50):
        self._lock = threading.RLock()
        self.samples = deque()
        self.total = np.zeros(len(WAVELENGTHS))
        self.received = 0
        self.received_at = 0.0
        self.resize(capacity)

    def __len__(self):
        with self._lock:
            return len(self.samples)

    def resize(self, capacity):
        if not 1 <= capacity <= MAX_SAMPLES:
            raise ValueError("A puffer mérete 1–{} lehet.".format(MAX_SAMPLES))
        with self._lock:
            self.capacity = capacity
            while len(self.samples) > capacity:
                self.total -= self.samples.popleft()

    def append(self, values):
        with self._lock:
            if len(self.samples) == self.capacity:
                self.total -= self.samples.popleft()
            self.samples.append(values.copy())
            self.total += values
            self.received += 1
            self.received_at = time.monotonic()
            if self.received % 4096 == 0:
                self.total = np.sum(self.samples, axis=0)

    def mean(self, window=None):
        with self._lock:
            if not self.samples:
                return np.zeros(len(WAVELENGTHS))
            if window == 1:
                return self.samples[-1].copy()
            if window is None or window >= len(self.samples):
                return self.total / len(self.samples)
            if window < 1:
                raise ValueError("Az átlagolási ablak legalább 1 minta legyen.")
            return np.mean(self.recent(window), axis=0)

    def recent(self, rows):
        with self._lock:
            return np.asarray(list(islice(self.samples, max(0, len(self.samples) - rows), None)))

    def snapshot(self, average=1, rows=0):
        """One consistent frame. History size never implicitly enables averaging."""
        with self._lock:
            return SpectrumSnapshot(self.mean(average), self.recent(rows), len(self.samples),
                                    self.capacity, self.received, self.received_at)

    def save_csv(self, path):
        # Release the acquisition lock before any potentially slow disk I/O.
        with self._lock:
            samples = list(self.samples)
        with Path(path).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["{}nm".format(w) for w in WAVELENGTHS])
            writer.writerows(samples)


class Acquisition(threading.Thread):
    """Store samples immediately; GUI rendering cannot back up serial input."""
    def __init__(self, events, port, baud, demo=False, buffer=None):
        super().__init__(name="spectread-acquisition", daemon=True)
        self.events = events
        self.port, self.baud, self.demo = port, baud, demo
        self.buffer = buffer if buffer is not None else SpectrumBuffer()
        self.suppressed_messages = 0
        self.stop_event = threading.Event()

    def emit(self, kind, payload):
        # Diagnostics must never stop measurement or fill the OS serial buffer.
        if self.stop_event.is_set():
            return False
        try:
            self.events.put_nowait((kind, payload))
            return True
        except queue.Full:
            if kind == "message":
                self.suppressed_messages += 1
                return False
            # Preserve connection/error notifications by evicting one old message.
            try:
                self.events.get_nowait()
            except queue.Empty:
                pass
            self.events.put_nowait((kind, payload))
            return True

    def run(self):
        try:
            if self.demo:
                self.emit("ready", "DEMÓ · szimulált adatok")
                step = 0
                x = np.arange(18)
                while not self.stop_event.is_set():
                    values = 120 + 650 * np.exp(-((x - (8 + 4 * np.sin(step / 24))) / 3.8) ** 2)
                    values += 35 * np.sin(x + step / 7)
                    self.buffer.append(values)
                    step += 1
                    self.stop_event.wait(0.1)
                return
            with serial.serial_for_url(self.port, baudrate=self.baud, timeout=0.05,
                                       write_timeout=0.2) as connection:
                self.emit("ready", "{} · {} baud".format(self.port, self.baud))
                pending = bytearray()
                discarding = False
                while not self.stop_event.is_set():
                    block = connection.read(min(max(connection.in_waiting, 1), 65536))
                    fragments = block.split(b"\n")
                    for index, fragment in enumerate(fragments):
                        if self.stop_event.is_set():
                            break
                        if not discarding:
                            if len(pending) + len(fragment) > MAX_LINE_BYTES:
                                pending.clear()
                                discarding = True
                                self.emit("message", "Túl hosszú sor kihagyva (4096 bájt felett).")
                            else:
                                pending.extend(fragment)
                        if index == len(fragments) - 1:
                            continue  # Last fragment may be an unfinished serial line.
                        if not discarding and pending:
                            line = pending.decode("utf-8", errors="replace").strip()
                            values = parse_sample(line)
                            if values is not None:
                                self.buffer.append(values)
                            else:
                                self.emit("message", line[:240])
                        pending.clear()
                        discarding = False
        except (serial.SerialException, OSError, ValueError) as exc:
            self.emit("error", str(exc))
