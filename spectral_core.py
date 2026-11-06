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
from device_protocol import DeviceProtocol, parse_message

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

    def clear(self):
        with self._lock:
            self.samples.clear()
            self.total.fill(0)
            self.received_at = 0.0

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
        self.protocol = DeviceProtocol()

    def command(self, op, *args):
        return self.protocol.request(op, *args)

    def _device_message(self, message):
        previous = self.protocol.state
        if message["type"] == "state" and previous and any(
                previous[key] != message[key] for key in ("gain", "cycles", "format")):
            self.buffer.clear()  # Never average/export mixed gain or data formats.
        acknowledged = self.protocol.accept(message)
        self.emit("device", dict(message, acknowledged=acknowledged))

    def _commands(self, connection, now):
        for notice in self.protocol.take_cancelled():
            self.emit("device", notice)
        for _ in range(4):
            item = self.protocol.next_command(now)
            if item is None:
                break
            written = connection.write(item.wire)
            if written != len(item.wire):
                raise serial.SerialTimeoutException("A panelparancs csak részben lett elküldve.")
        for timeout in self.protocol.expire(now):
            if timeout["command"] != "INFO":
                self.emit("device", timeout)

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
                self._device_message({"type": "hello", "id": 0, "protocol": 1,
                                      "device": "AS7265x", "firmware": "demo-1.0", "board": "Szimulátor",
                                      "sensor_ok": 1, "caps": ["LED", "IND", "SET", "TEMP", "RUN", "SHOT", "OFF", "PING"]})
                state = {"type": "state", "id": 0, "gain": 2, "cycles": 10,
                         "format": "calibrated", "stream": 1, "led": [0, 0, 0], "current": [0, 0, 0],
                         "indicator": [0, 0, 0], "indicator_current": [0, 0, 0]}
                self._device_message(dict(state))
                step = 0
                x = np.arange(18)
                next_sample = 0.0
                single_shot = False
                while not self.stop_event.is_set():
                    now = time.monotonic()
                    for notice in self.protocol.take_cancelled():
                        self.emit("device", notice)
                    item = self.protocol.next_command(now)
                    if item:
                        tokens = item.wire.decode("ascii").split()
                        op, args = tokens[1], tokens[2:]
                        state = dict(state, id=item.id)
                        if op in {"LED", "IND"}:
                            enabled, current = ("led", "current") if op == "LED" else ("indicator", "indicator_current")
                            state[enabled] = list(state[enabled]); state[current] = list(state[current])
                            state[enabled][int(args[0])] = int(args[1]); state[current][int(args[0])] = int(args[2])
                        elif op == "OFF":
                            state["led"] = [0, 0, 0]; state["indicator"] = [0, 0, 0]
                        elif op == "SET":
                            state.update(gain=int(args[0]), cycles=int(args[1]), format=args[2])
                        elif op == "RUN":
                            state["stream"] = int(args[0])
                        elif op == "SHOT":
                            single_shot = True
                        if op == "INFO":
                            self._device_message(dict(self.protocol.hello, id=item.id))
                        elif op == "TEMP":
                            self._device_message({"type": "temperature", "id": item.id, "values": [25, 26, 25]})
                        else:
                            self._device_message(dict(state))
                    if (state["stream"] or single_shot) and now >= next_sample:
                        values = 120 + 650 * np.exp(-((x - (8 + 4 * np.sin(step / 24))) / 3.8) ** 2)
                        values += 35 * np.sin(x + step / 7)
                        if state["format"] == "raw":
                            values = np.clip(values * 10, 0, 65535).astype(int).astype(float)
                        self.buffer.append(values)
                        step += 1; single_shot = False
                        next_sample = now + max(0.02, state["cycles"] * 0.0056)
                    self.stop_event.wait(0.01)
                return
            with serial.serial_for_url(self.port, baudrate=self.baud, timeout=0.05,
                                       write_timeout=0.2) as connection:
                self.emit("ready", "{} · {} baud".format(self.port, self.baud))
                next_probe = time.monotonic()
                probes = 0
                last_ping = 0.0
                pending = bytearray()
                discarding = False
                while not self.stop_event.is_set():
                    now = time.monotonic()
                    if not self.protocol.hello and probes < 3 and now >= next_probe and hasattr(connection, "write"):
                        self.protocol.request("INFO")
                        probes += 1; next_probe = now + 1.5
                    if self.protocol.available and now - last_ping >= 2 and "PING" in self.protocol.hello["caps"]:
                        connection.write(b"@0 PING\n")
                        last_ping = now
                    self._commands(connection, now)
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
                            message = parse_message(line)
                            values = None if message else parse_sample(line)
                            if message:
                                self._device_message(message)
                            elif values is not None:
                                self.buffer.append(values)
                            else:
                                self.emit("message", line[:240])
                        pending.clear()
                        discarding = False
                if self.protocol.available:
                    # Best effort on close; the firmware also times out illumination
                    # after missing host heartbeats. Do not wait for a reply here.
                    connection.write(b"@0 OFF\n")
        except (serial.SerialException, OSError, ValueError) as exc:
            self.emit("error", str(exc))
