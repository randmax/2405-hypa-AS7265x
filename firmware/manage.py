"""Build or explicitly upload Nano firmware; a build never touches a serial port."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if __name__ == "__main__":
    from bootstrap import bootstrap_or_exit
    bootstrap_or_exit()

import argparse
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
PROFILES = {"nano": "arduino:avr:nano:cpu=atmega328",
            "nano-old": "arduino:avr:nano:cpu=atmega328old"}


def build(cli, profile, output):
    installed = subprocess.run([cli, "core", "list", "--format", "json"], check=True,
                               capture_output=True, text=True, encoding="utf-8")
    platforms = json.loads(installed.stdout).get("platforms", [])
    version = next((p.get("installed_version") for p in platforms if p.get("id") == "arduino:avr"), None)
    if version != "1.8.6":
        raise RuntimeError("Arduino AVR Boards 1.8.6 szükséges: arduino-cli core install arduino:avr@1.8.6")
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([cli, "compile", "--fqbn", PROFILES[profile], "--export-binaries",
                    "--output-dir", str(output), str(ROOT / "AS7265xController")], check=True)
    paths = [output / "AS7265xController.ino.hex", output / "AS7265xController.ino.with_bootloader.hex"]
    if not all(path.is_file() for path in paths):
        raise RuntimeError("Az Arduino core nem hozta létre mindkét HEX fájlt.")
    for path in paths:
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    manifest = {"profile": profile, "fqbn": PROFILES[profile], "core": "arduino:avr@1.8.6",
                "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted((ROOT / "AS7265xController").glob("*")) if p.is_file()},
                "files": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return paths[0]


def main():
    parser = argparse.ArgumentParser(description="AS7265x Nano build / UART upload")
    parser.add_argument("operation", choices=("build", "upload", "burn-bootloader"))
    parser.add_argument("--board", choices=PROFILES, default="nano")
    parser.add_argument("--cli", default="arduino-cli", help="Arduino CLI executable")
    parser.add_argument("--port", help="COM3 or /dev/ttyUSB0; required for actual programming")
    parser.add_argument("--programmer", help="ISP programmer ID (only burn-bootloader)")
    parser.add_argument("--output", type=Path, help="Build output directory")
    args = parser.parse_args()
    cli = shutil.which(args.cli)
    if not cli:
        parser.error("Arduino CLI nem található. Telepítsd, vagy add meg: --cli TELJES_ÚTVONAL")
    if args.operation != "build" and not args.port:
        parser.error("Feltöltéshez/programozáshoz --port szükséges.")
    if args.operation == "burn-bootloader" and not args.programmer:
        parser.error("Bootloader írásához külön ISP és --programmer szükséges; ez nem UART-feltöltés.")
    output = (args.output or ROOT / "build" / args.board).resolve()
    try:
        if args.operation == "burn-bootloader":
            subprocess.run([cli, "burn-bootloader", "--fqbn", PROFILES[args.board],
                            "--programmer", args.programmer, "--port", args.port], check=True)
        else:
            sketch = build(cli, args.board, output)
            if args.operation == "upload":
                # Upload only the application image through the existing bootloader.
                subprocess.run([cli, "upload", "--fqbn", PROFILES[args.board], "--port", args.port,
                                "--input-file", str(sketch)], check=True)
        print("Kész: {} ({})".format(args.operation, args.board))
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, "Firmware-művelet sikertelen: {}\n".format(exc))


if __name__ == "__main__":
    main()
