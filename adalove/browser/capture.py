from __future__ import annotations

from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

_ADALOVE_URL = "https://adalove.inteli.edu.br/"
_API_HOST = "apiv2.inteli.edu.br/sections/"
_API_PATH = "/userdata"
_PROFILE_DIR = Path.home() / ".adalove-browser"
_TIMEOUT_MS = 8_000


def _best_response(captured: list[tuple[str, str, int]]) -> tuple[str, str]:
    raise NotImplementedError


def capture_credentials() -> tuple[str, str]:
    raise NotImplementedError
