"""Standard-library-only startup: always run in this project's virtualenv."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

PROJECT = Path(__file__).resolve().parent
VENV = PROJECT / (".venv" if os.name == "nt" else ".venv-linux")


def venv_python():
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv():
    """Create/install once, then re-execute the original entry point in the venv."""
    if sys.version_info < (3, 9):
        raise RuntimeError("Python 3.9 vagy újabb szükséges.")
    python = venv_python()
    # Compare prefixes, not resolved executables: Linux venv Python is a symlink.
    inside = Path(sys.prefix).absolute() == VENV.absolute() and sys.prefix != sys.base_prefix
    if not inside:
        if not python.exists():
            print("Virtuális környezet létrehozása: {}".format(VENV), flush=True)
            try:
                venv.EnvBuilder(with_pip=True).create(VENV)
            except (OSError, subprocess.SubprocessError) as exc:
                raise RuntimeError(
                    "Nem hozható létre a venv. Linuxon telepítsd a python3-venv "
                    "csomagot, és ellenőrizd a projekt írási jogát. {}".format(exc)
                ) from exc
        probe = subprocess.run(
            [str(python), "-X", "utf8", "-c",
             "import sys; sys.stdout.reconfigure(encoding='utf-8'); print(sys.prefix)"],
            capture_output=True, text=True, encoding="utf-8")
        if probe.returncode or Path(probe.stdout.strip()).absolute() != VENV.absolute():
            raise RuntimeError("A meglévő venv nem használható: {}. Nevezd át, majd indítsd újra."
                               .format(VENV))
        command = [str(python), "-X", "utf8", str(Path(sys.argv[0]).resolve()), *sys.argv[1:]]
        if os.name != "nt":
            os.execv(str(python), command)
        try:
            raise SystemExit(subprocess.call(command))
        except KeyboardInterrupt:
            raise SystemExit(130)

    requirements = PROJECT / "requirements.txt"
    digest = hashlib.sha256(requirements.read_bytes() +
                            str(sys.version_info[:2]).encode("ascii")).hexdigest()
    marker = VENV / ".spectread-requirements.sha256"
    installed = marker.read_text().strip() if marker.exists() else ""
    probe = subprocess.run([sys.executable, "-X", "utf8", "-c", "import serial, numpy, matplotlib"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if installed != digest or probe.returncode:
        print("Függőségek ellenőrzése / telepítése a venv-be…", flush=True)
        subprocess.check_call([sys.executable, "-X", "utf8", "-m", "pip", "install", "-r", str(requirements)])
        marker.write_text(digest, encoding="ascii")
    try:
        import tkinter  # noqa: F401 -- provided by the OS, not pip
    except ImportError as exc:
        raise RuntimeError(
            "Hiányzik a Tk. Debian/Ubuntu: sudo apt install python3-tk python3-venv. "
            "Fedora: sudo dnf install python3-tkinter. Windows: Python telepítő → Tcl/Tk."
        ) from exc


def bootstrap_or_exit():
    # Redirected Windows consoles may use cp1252, which cannot encode Hungarian
    # text. Configure this process too, before its first startup/error message.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        ensure_venv()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print("Indítási hiba: {}".format(exc), file=sys.stderr)
        raise SystemExit(1)
