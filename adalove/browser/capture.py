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
    """Pick the entry with the largest response body from (url, auth, body_size) list."""
    if not captured:
        raise TimeoutError(
            "No API request was captured within the timeout. "
            "Make sure you are logged into Adalove and try again."
        )
    url, auth, _ = max(captured, key=lambda x: x[2])
    if not auth:
        raise ValueError("Captured request had no Authorization header.")
    return url, auth


def capture_credentials() -> tuple[str, str]:
    """Return (api_url, bearer_token) by intercepting the Adalove network request.

    Raises:
        ImportError: playwright package not installed.
        PermissionError: browser redirected away from Adalove (user not logged in).
        TimeoutError: no matching request captured within 8 seconds.
        ValueError: matching request had no Authorization header.
    """
    if not _PLAYWRIGHT_AVAILABLE:
        raise ImportError(
            "Playwright is not installed. "
            "Run: pip install playwright && playwright install chromium"
        )

    captured: list[tuple[str, str, int]] = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(_PROFILE_DIR),
            headless=False,
        )

        def _on_response(response) -> None:
            if _API_HOST not in response.url or _API_PATH not in response.url:
                return
            try:
                auth = response.request.headers.get("authorization", "")
                body_size = len(response.body())
                if auth:
                    captured.append((response.url, auth, body_size))
            except Exception:  # noqa: BLE001
                pass

        context.on("response", _on_response)
        page = context.new_page()
        try:
            page.goto(_ADALOVE_URL, wait_until="domcontentloaded", timeout=15_000)

            if not page.url.startswith(_ADALOVE_URL):
                raise PermissionError(
                    "Not logged in — open Adalove in your browser, log in, then re-run setup."
                )

            try:
                page.click("text=Atividades", timeout=5_000)
            except Exception:  # noqa: BLE001
                pass

            page.wait_for_timeout(_TIMEOUT_MS)
        finally:
            context.close()

    return _best_response(captured)
