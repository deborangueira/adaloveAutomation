"""Every filesystem location the app uses, defined once.

The app runs from its own checkout (`pip install -e .`), so config and
output live next to the code, as they always have.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Holds the Adalove bearer token — written owner-only (see settings.py).
CONFIG_PATH = PROJECT_ROOT / "config.json"

# Default destination for generated dashboards and Markdown files.
OUTPUT_DIR = PROJECT_ROOT / "output"

# Dedicated Chromium profile that keeps the Adalove login between captures.
BROWSER_PROFILE_DIR = Path.home() / ".adalove-browser"

# PID of the running `adalove serve`, so a new one can replace it.
SERVER_PIDFILE = Path.home() / ".adalove-server.pid"
