"""Versioned ASCII control protocol alongside the legacy 18-column CSV stream."""
from collections import deque
from dataclasses import dataclass
import json
import threading

COMMANDS = {"INFO", "STATE", "LED", "IND", "SET", "TEMP", "RUN", "SHOT", "OFF", "PING"}


def _int(value, low, high):
    return type(value) is int and low <= value <= high


def command_text(op, args=()):
    if op not in COMMANDS:
        raise ValueError("Ismeretlen panelparancs.")
    valid = False
    if op in {"INFO", "STATE", "TEMP", "SHOT", "OFF", "PING"}:
        valid = not args
    elif op in {"LED", "IND"}:
        valid = (len(args) == 3 and _int(args[0], 0, 2) and
                 _int(args[1], 0, 1) and _int(args[2], 0, 3))
    elif op == "RUN":
        valid = len(args) == 1 and _int(args[0], 0, 1)
    elif op == "SET":
        valid = (len(args) == 3 and _int(args[0], 0, 3) and
                 _int(args[1], 1, 256) and args[2] in ("raw", "calibrated"))
    if not valid:
        raise ValueError("Érvénytelen panelparancs vagy beállítási tartomány.")
    return " ".join([op, *map(str, args)])


def parse_message(line):
    if not line.startswith("#{"):
        return None
    try:
        value = json.loads(line[1:])
    except (ValueError, TypeError):
        return None
    if not isinstance(value, dict) or not _int(value.get("id", 0), 0, 65535):
        return None
    kind = value.get("type")
    if kind == "hello":
        valid = (_int(value.get("protocol"), 1, 1) and value.get("device") == "AS7265x" and
                 isinstance(value.get("firmware"), str) and len(value["firmware"]) <= 64 and
                 isinstance(value.get("board"), str) and len(value["board"]) <= 64 and
                 _int(value.get("sensor_ok"), 0, 1) and isinstance(value.get("caps"), list) and
                 all(isinstance(op, str) and op in COMMANDS for op in value["caps"]))
    elif kind == "state":
        valid = (_int(value.get("gain"), 0, 3) and _int(value.get("cycles"), 1, 256) and
                 value.get("format") in ("raw", "calibrated") and _int(value.get("stream"), 0, 1))
        for field, high in (("led", 1), ("current", 3), ("indicator", 1), ("indicator_current", 3)):
            values = value.get(field)
            valid = valid and isinstance(values, list) and len(values) == 3 and all(
                _int(item, 0, high) for item in values)
    elif kind == "temperature":
        values = value.get("values")
        valid = isinstance(values, list) and len(values) == 3 and all(_int(item, -127, 127) for item in values)
    elif kind == "error":
        valid = isinstance(value.get("message"), str) and len(value["message"]) <= 240
    elif kind == "pong":
        valid = True
    else:
        valid = False
    return value if valid else None


@dataclass
class PendingCommand:
    id: int
    op: str
    wire: bytes
    sent_at: float = 0.0


class DeviceProtocol:
    def __init__(self):
        self.lock = threading.RLock()
        self.outgoing = deque()
        self.pending = {}
        self.cancelled = deque(maxlen=32)
        self.sequence = 0
        self.hello = None
        self.state = None

    @property
    def available(self):
        with self.lock:
            return bool(self.hello and self.hello["sensor_ok"])

    def request(self, op, *args):
        text = command_text(op, args)
        with self.lock:
            if op not in {"INFO", "STATE"} and (not self.available or op not in self.hello["caps"]):
                raise ValueError("Ehhez a vezérléshez az új AS7265xController firmware szükséges.")
            if op == "OFF":
                retained = deque()
                for item in self.outgoing:
                    if item.op in {"LED", "IND", "OFF"}:
                        self.cancelled.append(item)
                    else:
                        retained.append(item)
                self.outgoing = retained
                if len(self.outgoing) + len(self.pending) >= 16 and self.outgoing:
                    self.cancelled.append(self.outgoing.pop())
            if len(self.outgoing) + len(self.pending) >= 16:
                raise ValueError("A panel parancssora megtelt; várd meg a visszajelzést.")
            for _ in range(65535):
                self.sequence = self.sequence % 65535 + 1
                if self.sequence not in self.pending and all(c.id != self.sequence for c in self.outgoing):
                    break
            item = PendingCommand(self.sequence, op, "@{} {}\n".format(self.sequence, text).encode("ascii"))
            if op == "OFF":
                self.outgoing.appendleft(item)
            else:
                self.outgoing.append(item)
            return item.id

    def take_cancelled(self):
        with self.lock:
            result = [{"type": "cancelled", "id": item.id, "command": item.op,
                       "message": "A kikapcsolás felülírta a még el nem küldött parancsot."}
                      for item in self.cancelled]
            self.cancelled.clear()
            return result

    def next_command(self, now):
        with self.lock:
            if not self.outgoing or len(self.pending) >= 4:
                return None
            item = self.outgoing.popleft()
            item.sent_at = now
            self.pending[item.id] = item
            return item

    def accept(self, message):
        with self.lock:
            kind = message["type"]
            if kind == "hello":
                self.hello = message
            elif kind == "state":
                self.state = message
            item = self.pending.get(message.get("id"))
            expected = ("hello" if item and item.op == "INFO" else
                        "temperature" if item and item.op == "TEMP" else
                        "pong" if item and item.op == "PING" else "state")
            if item and kind in {expected, "error"}:
                del self.pending[item.id]
                return item.op
            return None

    def expire(self, now):
        with self.lock:
            expired = [item for item in self.pending.values() if now - item.sent_at >= 3.0]
            for item in expired:
                del self.pending[item.id]
            return [{"type": "timeout", "id": item.id, "command": item.op,
                     "message": "A panel nem igazolta vissza a parancsot."} for item in expired]
