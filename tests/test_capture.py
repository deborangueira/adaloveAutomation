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
    with pytest.raises(TimeoutError, match="No API request"):
        _best_response([])


def test_best_response_empty_auth_raises_value_error():
    with pytest.raises(ValueError, match="Authorization header"):
        _best_response([("https://api/sections/aaa/userdata", "", 100)])


from unittest.mock import patch


def test_capture_credentials_raises_import_error_when_unavailable():
    with patch("adalove.browser.capture._PLAYWRIGHT_AVAILABLE", False):
        from adalove.browser.capture import capture_credentials
        with pytest.raises(ImportError, match="playwright install chromium"):
            capture_credentials()
