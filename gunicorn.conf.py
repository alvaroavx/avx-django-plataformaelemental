"""Expose the source packages before Gunicorn loads the WSGI application."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
