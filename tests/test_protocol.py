import copy
import json
import unittest

from device_protocol import DeviceProtocol, command_text, parse_message

HELLO = {"type": "hello", "id": 0, "protocol": 1, "device": "AS7265x", "firmware": "1.0.0",
         "board": "ATmega328P", "sensor_ok": 1,
         "caps": ["LED", "IND", "SET", "TEMP", "RUN", "SHOT", "OFF", "PING"]}
STATE = {"type": "state", "id": 0, "gain": 2, "cycles": 10, "format": "calibrated", "stream": 1,
         "led": [0, 0, 0], "current": [0, 0, 0], "indicator": [0, 0, 0], "indicator_current": [0, 0, 0]}


class ProtocolTests(unittest.TestCase):
    def test_validate_commands_and_reject_injection_or_invalid_ranges(self):
        self.assertEqual(command_text("LED", (2, 1, 3)), "LED 2 1 3")
        self.assertEqual(command_text("SET", (2, 256, "raw")), "SET 2 256 raw")
        for op, args in (("LED", (3, 1, 0)), ("LED", (1, -1, 0)), ("IND", (0, True, 0)),
                         ("SET", (4, 10, "raw")), ("SET", (2, 0, "raw")),
                         ("SET", (2, 10, "raw\n@1 OFF")), ("UNKNOWN", ()), ("OFF", (1,))):
            with self.subTest(op=op, args=args), self.assertRaises(ValueError):
                command_text(op, args)

    def test_validate_serial_payloads_before_ui_uses_them(self):
        for message in (HELLO, STATE, {"type": "temperature", "id": 3, "values": [-20, 0, 127]}):
            self.assertEqual(parse_message("#" + json.dumps(message)), message)
        bad = ["#{", "#[]", '#{"type":"state","format":[]}', "1,2,3"]
        for changes in ({"gain": 8}, {"led": [1]}, {"cycles": 257}, {"format": []}):
            bad.append("#" + json.dumps(dict(STATE, **changes)))
        bad.append("#" + json.dumps(dict(HELLO, protocol=2)))
        for line in bad:
            with self.subTest(line=line):
                self.assertIsNone(parse_message(line))

    def test_legacy_firmware_cannot_receive_actuator_commands(self):
        session = DeviceProtocol()
        with self.assertRaises(ValueError):
            session.request("LED", 0, 1, 0)
        request = session.request("INFO")
        self.assertEqual(session.next_command(1).wire, "@{} INFO\n".format(request).encode())

    def test_off_has_priority_and_removes_queued_led_enables(self):
        session = DeviceProtocol()
        session.accept(copy.deepcopy(HELLO))
        session.request("LED", 0, 1, 0)
        session.request("IND", 1, 1, 0)
        session.request("TEMP")
        request = session.request("OFF")
        self.assertEqual([n["command"] for n in session.take_cancelled()], ["LED", "IND"])
        first = session.next_command(1)
        self.assertEqual((first.id, first.op), (request, "OFF"))
        self.assertEqual(session.next_command(1).op, "TEMP")
        self.assertIsNone(session.next_command(1))

    def test_only_matching_response_acknowledges_and_timeouts_are_reported(self):
        session = DeviceProtocol()
        session.accept(copy.deepcopy(HELLO))
        request = session.request("LED", 0, 1, 0)
        session.next_command(10)
        self.assertIsNone(session.accept({"type": "temperature", "id": request, "values": [1, 2, 3]}))
        self.assertIn(request, session.pending)
        self.assertEqual(session.accept(dict(STATE, id=request)), "LED")
        session.request("TEMP")
        session.next_command(20)
        self.assertFalse(session.expire(22.9))
        self.assertEqual(session.expire(23)[0]["command"], "TEMP")

    def test_command_queue_is_bounded(self):
        session = DeviceProtocol()
        session.accept(copy.deepcopy(HELLO))
        for _ in range(16):
            session.request("TEMP")
        with self.assertRaises(ValueError):
            session.request("TEMP")
        session.request("OFF")
        self.assertEqual(session.next_command(0).op, "OFF")
