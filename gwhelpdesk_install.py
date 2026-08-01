#!/usr/bin/env python3
"""Create a local virtual environment and prepare gwhelpdesk.

OS package installation, reverse-proxy configuration, and service management are
intentionally kept outside this script so deployments can use the platform's
supported Python, nginx, and systemd packages.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

MIN_VERSION = (3, 10)
ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    if sys.version_info < MIN_VERSION:
        print(
            f"Python {MIN_VERSION[0]}.{MIN_VERSION[1]} or newer is required; "
            f"found {sys.version.split()[0]}",
            file=sys.stderr,
        )
        return 2

    if not VENV.exists():
        run(sys.executable, "-m", "venv", str(VENV))

    python = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run(str(python), "-m", "pip", "install", "--upgrade", "pip")
    run(str(python), "-m", "pip", "install", "-r", "requirements.txt")
    run(str(python), "manage.py", "migrate")
    run(str(python), "manage.py", "check")

    print()
    print("Installation prepared successfully.")
    print(f"Activate the virtual environment under {VENV}")
    print("Then run: python manage.py setup")
    print("For a test server: python manage.py runserver 0.0.0.0:8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
