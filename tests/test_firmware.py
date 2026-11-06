import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from device_protocol import parse_message
from spectral_core import parse_sample

ROOT = Path(__file__).resolve().parents[1]


class FirmwareTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "Native firmware harness needs g++ (Linux CI)")
    def test_actual_sketch_with_virtual_i2c_and_serial_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "firmware-test"
            compiled = subprocess.run(["g++", "-std=c++17", "-O2", "-D__AVR_ATmega328P__",
                                       "-I", str(ROOT / "tests/firmware/mock"),
                                       str(ROOT / "tests/firmware/harness.cpp"), "-o", str(binary)],
                                      capture_output=True, text=True, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        messages = []
        samples = []
        for line in result.stdout.splitlines():
            if line.startswith("#"):
                message = parse_message(line)
                self.assertIsNotNone(message, line)
                messages.append(message)
            else:
                sample = parse_sample(line)
                self.assertIsNotNone(sample, line)
                samples.append(sample)
        self.assertTrue(any(m["type"] == "hello" and m["board"] == "ATmega328P" for m in messages))
        self.assertTrue(any(m["id"] == 6 and m["type"] == "error" for m in messages))
        self.assertTrue(any(m["id"] == 7 and m.get("values") == [25, 26, -12] for m in messages))
        self.assertTrue(any(m["id"] == 13 and m["type"] == "state" for m in messages))
        self.assertTrue(samples)

    def test_released_hex_checksums_sources_and_bootloader_region(self):
        for profile in ("nano", "nano-old"):
            directory = ROOT / "firmware/releases" / profile
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            for name, checksum in manifest["source_sha256"].items():
                source = ROOT / "firmware/AS7265xController" / name
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), checksum)
            for name, checksum in manifest["files"].items():
                data = (directory / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), checksum)
                addresses = []
                for line in data.decode("ascii").splitlines():
                    record = bytes.fromhex(line[1:])
                    self.assertEqual(sum(record) & 255, 0, "Invalid Intel HEX checksum")
                    if record[3] == 0 and record[0]:
                        addresses.append(int.from_bytes(record[1:3], "big"))
                self.assertTrue(addresses)
                if "with_bootloader" in name:
                    self.assertGreaterEqual(max(addresses), 0x7800)
