"""Bounded data storage and serial I/O; this module never touches Tk widgets."""

from collections import deque
import csv
from itertools import islice
import math
from pathlib import Path
import queue
import threading

import numpy as np
import serial

WAVELENGTHS = (410, 435, 460, 485, 510, 535, 560, 585, 610,
               645, 680, 705, 730, 760, 810, 860, 900, 940)
MAX_SAMPLES = 10000
MAX_LINE_BYTES = 4096


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
        self.samples = deque()
        self.total = np.zeros(len(WAVELENGTHS))
        self.received = 0
        self.resize(capacity)

    def __len__(self):
        return len(self.samples)

    def resize(self, capacity):
        if not 1 <= capacity <= MAX_SAMPLES:
            raise ValueError("A puffer mérete 1–{} lehet.".format(MAX_SAMPLES))
        self.capacity = capacity
        while len(self.samples) > capacity:
            self.total -= self.samples.popleft()

    def append(self, values):
        if len(self.samples) == self.capacity:
            self.total -= self.samples.popleft()
        self.samples.append(values.copy())
        self.total += values
        self.received += 1
        if self.received % 4096 == 0:
            self.total = np.sum(self.samples, axis=0)

    def mean(self):
        return self.total / len(self.samples) if self.samples else np.zeros(len(WAVELENGTHS))

    def recent(self, rows):
        return np.asarray(list(islice(self.samples, max(0, len(self.samples) - rows), None)))

    def save_csv(self, path):
        with Path(path).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["{}nm".format(w) for w in WAVELENGTHS])
            writer.writerows(self.samples)


class Acquisition(threading.Thread):
    """One cancellable producer with a bounded queue and bounded line assembly."""
    def __init__(self, events, port, baud, demo=False):
        super().__init__(name="spectread-acquisition", daemon=True)
        self.events = events
        self.port, self.baud, self.demo = port, baud, demo
        self.stop_event = threading.Event()

    def emit(self, kind, payload):
        while not self.stop_event.is_set():
            try:
                self.events.put((kind, payload), timeout=0.1)
                return True
            except queue.Full:
                continue
        return False

    def run(self):
        try:
            if self.demo:
                self.emit("ready", "DEMÓ · szimulált adatok")
                step = 0
                x = np.arange(18)
                while not self.stop_event.is_set():
                    values = 120 + 650 * np.exp(-((x - (8 + 4 * np.sin(step / 24))) / 3.8) ** 2)
                    values += 35 * np.sin(x + step / 7)
                    self.emit("sample", values)
                    step += 1
                    self.stop_event.wait(0.1)
                return
            with serial.serial_for_url(self.port, baudrate=self.baud, timeout=0.2,
                                       write_timeout=0.2) as connection:
                self.emit("ready", "{} · {} baud".format(self.port, self.baud))
                pending = bytearray()
                discarding = False
                while not self.stop_event.is_set():
                    block = connection.read(min(max(connection.in_waiting, 1), 4096))
                    for byte in block:
                        if byte == 10:
                            if not discarding and pending:
                                line = pending.decode("utf-8", errors="replace").strip()
                                values = parse_sample(line)
                                self.emit("sample" if values is not None else "message",
                                          values if values is not None else line[:240])
                            pending.clear()
                            discarding = False
                        elif not discarding:
                            pending.append(byte)
                            if len(pending) > MAX_LINE_BYTES:
                                pending.clear()
                                discarding = True
                                self.emit("message", "Túl hosszú sor kihagyva (4096 bájt felett).")
        except (serial.SerialException, OSError, ValueError) as exc:
            self.emit("error", str(exc))
