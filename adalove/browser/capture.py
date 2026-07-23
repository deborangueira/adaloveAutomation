from __future__ import annotations

import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

_ADALOVE_URL = "https://adalove.inteli.edu.br/academic-life"
_API_HOST = "apiv2.inteli.edu.br/sections/"
_API_PATH = "/userdata"
_PROFILE_DIR = Path.home() / ".adalove-browser"
_POLL_MS = 300
_LOGIN_WAIT_MS = 180_000


def _best_response(captured: list[tuple[str, str, int]]) -> tuple[str, str]:
    """Pick the entry with the largest response body from (url, auth, body_size) list."""
    if not captured:
        raise TimeoutError(
            "Nenhuma requisição da API foi capturada dentro do tempo limite. "
            "Certifique-se de estar logado no Adalove e tente novamente."
        )
    url, auth, _ = max(captured, key=lambda x: x[2])
    if not auth:
        raise ValueError("A requisição capturada não possui cabeçalho de autorização.")
    return url, auth


def capture_credentials() -> tuple[str, str]:
    """Return (api_url, bearer_token) by intercepting the Adalove network request.

    Raises:
        ImportError: playwright package not installed.
        PermissionError: user not logged in and didn't log in within the wait window.
        TimeoutError: no matching request captured, or any browser/network error.
        ValueError: matching request had no Authorization header.
    """
    if not _PLAYWRIGHT_AVAILABLE:
        raise ImportError(
            "Playwright não está instalado. "
            "Execute: pip install playwright && playwright install chromium"
        )

    captured: list[tuple[str, str, int]] = []

    try:
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
                # Navigating straight to /academic-life triggers the userdata request
                # once authenticated — whether that happens instantly (existing session)
                # or after a manual Google login (may bounce through accounts.google.com
                # first), so we just poll for the capture instead of relying on any
                # particular UI marker, which breaks every time Adalove's layout changes.
                page.goto(_ADALOVE_URL, wait_until="domcontentloaded", timeout=15_000)

                deadline = time.monotonic() + _LOGIN_WAIT_MS / 1000
                while not captured and time.monotonic() < deadline:
                    page.wait_for_timeout(_POLL_MS)

                if not captured:
                    raise PermissionError(
                        "Login não detectado — faça login na janela do navegador que abriu "
                        "e execute o comando novamente."
                    )
            finally:
                context.close()
    except (PermissionError, TimeoutError):
        raise
    except Exception as exc:
        raise TimeoutError(f"Falha na captura pelo navegador: {exc}") from exc

    return _best_response(captured)
