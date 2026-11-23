from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time

from adalove.config.paths import BROWSER_PROFILE_DIR

try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

_ADALOVE_URL = "https://adalove.inteli.edu.br/academic-life"
_API_HOST = "apiv2.inteli.edu.br/sections/"
_API_PATH = "/userdata"
_PROFILE_DIR = BROWSER_PROFILE_DIR
_POLL_MS = 300
_LOGIN_WAIT_MS = 180_000
# Hard ceiling for the isolated capture: the login window plus slack for
# launching Chromium and the initial page load. Past this, the child (and its
# whole process group — Playwright driver + Chromium) is killed.
_ISOLATED_TIMEOUT_S = _LOGIN_WAIT_MS / 1000 + 60

_ERROR_TYPES: dict[str, type[Exception]] = {
    "ImportError": ImportError,
    "PermissionError": PermissionError,
    "TimeoutError": TimeoutError,
    "ValueError": ValueError,
}

_active_children: set[subprocess.Popen] = set()
_active_lock = threading.Lock()


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


def capture_credentials_isolated(timeout: float = _ISOLATED_TIMEOUT_S) -> tuple[str, str]:
    """Same contract as capture_credentials(), but runs it in a child process
    with a hard timeout.

    Meant for long-lived callers (the local web server): if Playwright hangs —
    e.g. the venv's playwright was upgraded under a server that has been
    running for days — the child is killed along with its driver/Chromium
    instead of pinning a request thread (and a stray driver) forever.
    """
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in sys.path if p))
    proc = subprocess.Popen(
        [sys.executable, "-m", "adalove.browser.capture"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,  # own process group, so we can kill driver + Chromium too
    )
    with _active_lock:
        _active_children.add(proc)
    try:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            raise TimeoutError(
                f"A captura pelo navegador não terminou em {int(timeout)}s e foi cancelada."
            ) from None
    finally:
        with _active_lock:
            _active_children.discard(proc)
    return _parse_child_output(out, err)


def kill_active_captures() -> None:
    """Kill any isolated capture still running — called when the server exits so
    no Chromium/driver outlives it."""
    with _active_lock:
        procs = list(_active_children)
    for proc in procs:
        _kill_tree(proc)


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, AttributeError):
        # AttributeError: no killpg on Windows — fall back to the child alone.
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    try:
        proc.communicate(timeout=5)
    except (subprocess.TimeoutExpired, ValueError):
        pass


def _parse_child_output(out: str, err: str) -> tuple[str, str]:
    lines = [line for line in (out or "").splitlines() if line.strip()]
    try:
        result = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError):
        detail = (err or "").strip()[-500:] or "sem saída"
        raise TimeoutError(f"Falha na captura pelo navegador: {detail}") from None
    if result.get("ok"):
        return result["api_url"], result["token"]
    exc_type = _ERROR_TYPES.get(result.get("error", ""), TimeoutError)
    raise exc_type(result.get("message", "Falha na captura pelo navegador."))


def _main() -> int:
    """Child-process entry point for capture_credentials_isolated(): prints a
    single JSON line with the result or the error."""
    try:
        api_url, token = capture_credentials()
        result = {"ok": True, "api_url": api_url, "token": token}
    except (ImportError, PermissionError, TimeoutError, ValueError) as e:
        result = {"ok": False, "error": type(e).__name__, "message": str(e)}
    print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
