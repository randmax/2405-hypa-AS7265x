import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class BootstrapTests(unittest.TestCase):
    def test_legacy_console_encoding_does_not_break_venv_startup(self):
        project = Path(__file__).resolve().parents[1]
        environment = dict(os.environ, PYTHONIOENCODING="cp1252")
        # Use the base Python to exercise venv selection, from a different cwd.
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys._base_executable, str(project / "start.py"), "--check-env"],
                cwd=directory, env=environment, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        self.assertIn("Környezet rendben.", result.stdout.decode("utf-8"))
        self.assertIn(str(project / (".venv" if os.name == "nt" else ".venv-linux")),
                      result.stdout.decode("utf-8"))
