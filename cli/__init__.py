"""Front-ends: the `adalove` terminal app (main.py + commands/) and the
local web server (server.py)."""

import sys
from pathlib import Path

# When the venv python binary is a symlink to the system interpreter, venv
# detection can fail and site-packages won't include the venv's packages.
# Add them explicitly so optional deps like playwright are always found.
# Lives here (not in main.py) so it runs before any cli module imports a
# third-party package.
_venv_lib = Path(__file__).resolve().parent.parent / ".venv" / "lib"
if _venv_lib.is_dir():
    for _d in _venv_lib.iterdir():
        _sp = _d / "site-packages"
        if _sp.is_dir() and str(_sp) not in sys.path:
            sys.path.insert(1, str(_sp))
