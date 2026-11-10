from unittest.mock import patch

import pytest
from adalove.browser.capture import _best_response


def test_best_response_picks_largest_body():
    captured = [
        ("https://api/sections/aaa/userdata", "Bearer token-a", 100),
        ("https://api/sections/bbb/userdata", "Bearer token-b", 500),
        ("https://api/sections/ccc/userdata", "Bearer token-c", 200),
    ]
    url, auth = _best_response(captured)
    assert url == "https://api/sections/bbb/userdata"
    assert auth == "Bearer token-b"


def test_best_response_single_entry():
    captured = [("https://api/sections/aaa/userdata", "Bearer only", 42)]
    url, auth = _best_response(captured)
    assert url == "https://api/sections/aaa/userdata"
    assert auth == "Bearer only"


def test_best_response_empty_raises_timeout():
    with pytest.raises(TimeoutError, match="Nenhuma requisição"):
        _best_response([])


def test_best_response_empty_auth_raises_value_error():
    with pytest.raises(ValueError, match="cabeçalho de autorização"):
        _best_response([("https://api/sections/aaa/userdata", "", 100)])


def test_capture_credentials_raises_import_error_when_unavailable():
    with patch("adalove.browser.capture._PLAYWRIGHT_AVAILABLE", False):
        from adalove.browser.capture import capture_credentials
        with pytest.raises(ImportError, match="playwright install chromium"):
            capture_credentials()


# ── capture_credentials_isolated ──────────────────────────────────────────────

import json
import subprocess
import sys

from adalove.browser import capture


def _fake_child(monkeypatch, code: str):
    """Make the isolated capture run `code` instead of the real Playwright child."""
    real_popen = subprocess.Popen

    def fake_popen(args, **kwargs):
        return real_popen([sys.executable, "-c", code], **kwargs)

    monkeypatch.setattr(capture.subprocess, "Popen", fake_popen)


def test_isolated_returns_credentials(monkeypatch):
    payload = json.dumps({"ok": True, "api_url": "https://api/sections/a/userdata", "token": "Bearer x"})
    _fake_child(monkeypatch, f"print({payload!r})")
    assert capture.capture_credentials_isolated(timeout=10) == ("https://api/sections/a/userdata", "Bearer x")


@pytest.mark.parametrize("name,exc", [
    ("PermissionError", PermissionError),
    ("ImportError", ImportError),
    ("ValueError", ValueError),
    ("TimeoutError", TimeoutError),
])
def test_isolated_reraises_child_error(monkeypatch, name, exc):
    payload = json.dumps({"ok": False, "error": name, "message": "boom"})
    _fake_child(monkeypatch, f"print({payload!r})")
    with pytest.raises(exc, match="boom"):
        capture.capture_credentials_isolated(timeout=10)


def test_isolated_garbage_output_raises_timeout(monkeypatch):
    _fake_child(monkeypatch, "import sys; sys.stderr.write('kaboom')")
    with pytest.raises(TimeoutError, match="kaboom"):
        capture.capture_credentials_isolated(timeout=10)


def test_isolated_kills_hung_child(monkeypatch):
    _fake_child(monkeypatch, "import time; time.sleep(60)")
    with pytest.raises(TimeoutError, match="cancelada"):
        capture.capture_credentials_isolated(timeout=0.5)
    assert not capture._active_children


def test_isolated_child_entry_point_reports_errors(monkeypatch, capsys):
    monkeypatch.setattr(capture, "_PLAYWRIGHT_AVAILABLE", False)
    assert capture._main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False and result["error"] == "ImportError"
