# Auto-Capture Credentials Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically capture the Adalove Bearer token and API URL by intercepting browser network requests, eliminating manual DevTools copy-paste on every token expiry.

**Architecture:** A new `adalove/browser/capture.py` module uses Playwright with a persistent Chromium profile (`~/.adalove-browser/`) to navigate to Adalove, intercept `apiv2.inteli.edu.br/sections/*/userdata` responses for 8 seconds, and return the URL + Authorization header from the largest response. `setup()` tries auto-capture first and falls back to manual prompts; `check()` triggers auto-capture on PermissionError before falling back to manual setup.

**Tech Stack:** Python, Playwright (sync API), pytest, pytest-mock

---

### Task 1: Add Playwright dependency and browser module skeleton

**Files:**
- Modify: `requirements.txt`
- Create: `adalove/browser/__init__.py`
- Create: `adalove/browser/capture.py`

- [ ] **Step 1: Add playwright to requirements.txt**

Open `requirements.txt` and add one line:

```
playwright>=1.40
```

Full file after edit:
```
typer>=0.12
questionary>=2.0
requests>=2.31
playwright>=1.40
pytest>=8.0
pytest-mock>=3.12
```

- [ ] **Step 2: Install playwright and browser binary**

```bash
pip install playwright && playwright install chromium
```

Expected: installs the package and downloads the Chromium binary to `~/.cache/ms-playwright/`.

- [ ] **Step 3: Create `adalove/browser/__init__.py`**

Create an empty file at `adalove/browser/__init__.py`.

- [ ] **Step 4: Create `adalove/browser/capture.py` stub**

```python
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
```

- [ ] **Step 5: Verify the module imports cleanly**

```bash
python -c "from adalove.browser.capture import capture_credentials; print('ok')"
```

Expected output: `ok`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt adalove/browser/__init__.py adalove/browser/capture.py
git commit -m "feat: add browser module skeleton and playwright dependency"
```

---

### Task 2: Implement `_best_response` and `capture_credentials`

**Files:**
- Modify: `adalove/browser/capture.py`
- Create: `tests/test_capture.py`

- [ ] **Step 1: Write failing tests for `_best_response`**

Create `tests/test_capture.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_capture.py -v
```

Expected: 4 failures — `NotImplementedError`.

- [ ] **Step 3: Implement `_best_response`**

Replace the stub in `adalove/browser/capture.py`:

```python
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
```

- [ ] **Step 4: Run tests to confirm `_best_response` passes**

```bash
pytest tests/test_capture.py -v
```

Expected: 4 passes.

- [ ] **Step 5: Write failing test for `capture_credentials` ImportError path**

Add to `tests/test_capture.py`:

```python
from unittest.mock import patch


def test_capture_credentials_raises_import_error_when_unavailable():
    with patch("adalove.browser.capture._PLAYWRIGHT_AVAILABLE", False):
        from adalove.browser.capture import capture_credentials
        with pytest.raises(ImportError, match="playwright install chromium"):
            capture_credentials()
```

- [ ] **Step 6: Run to confirm it fails**

```bash
pytest tests/test_capture.py::test_capture_credentials_raises_import_error_when_unavailable -v
```

Expected: FAIL — `NotImplementedError`.

- [ ] **Step 7: Implement `capture_credentials`**

Replace the stub in `adalove/browser/capture.py`:

```python
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
        page.goto(_ADALOVE_URL, wait_until="domcontentloaded", timeout=15_000)

        if not page.url.startswith(_ADALOVE_URL):
            context.close()
            raise PermissionError(
                "Not logged in — open Adalove in your browser, log in, then re-run setup."
            )

        try:
            page.click("text=Atividades", timeout=5_000)
        except Exception:  # noqa: BLE001
            pass

        page.wait_for_timeout(_TIMEOUT_MS)
        context.close()

    return _best_response(captured)
```

- [ ] **Step 8: Run all capture tests**

```bash
pytest tests/test_capture.py -v
```

Expected: 5 passes.

- [ ] **Step 9: Run full test suite to check for regressions**

```bash
pytest -v
```

Expected: all existing tests still pass.

- [ ] **Step 10: Commit**

```bash
git add adalove/browser/capture.py tests/test_capture.py
git commit -m "feat: implement capture_credentials with Playwright network interception"
```

---

### Task 3: Refactor `setup()` to use auto-capture

**Files:**
- Modify: `cli/main.py`

> **Note on the sidebar selector:** `page.click("text=Atividades")` uses Playwright's text selector. If the sidebar item label differs on the live site, update `_SIDEBAR_LABEL` in `capture.py` accordingly after inspecting the DOM. The click is wrapped in a try/except so a wrong label degrades gracefully — the page navigation still triggers requests.

- [ ] **Step 1: Extract `_run_setup` helper in `cli/main.py`**

Add this function just before the `@app.command() def setup()` definition (around line 334). It contains everything from the current `setup()` body after the manual prompts:

```python
def _run_setup(api_url: str, token: str) -> None:
    """Validate credentials and configure teacher mapping. Saves config on success."""
    token = token.strip()
    if not token.isascii():
        bad = [c for c in token if not c.isascii()]
        _err(
            f"Token contains non-ASCII characters {bad}.\n"
            "     In devtools, right-click the Authorization value → Copy Value."
        )
        raise typer.Exit(1)

    console.print()
    console.print("  Validating credentials...")
    try:
        client = AdaloveClient(api_url=api_url, token=token)
        activities = client.fetch_activities()
    except PermissionError as e:
        _err(str(e))
        raise typer.Exit(1)
    except (ConnectionError, ValueError) as e:
        _err(str(e))
        raise typer.Exit(1)

    _ok(f"{len(activities)} activities fetched.")

    teachers = get_unique_teachers(activities)
    if not teachers:
        _err("No teachers found in the response. Check your API URL.")
        raise typer.Exit(1)

    _section("Teacher Mapping")

    teacher_subjects: dict[str, str] = {}
    for teacher in teachers:
        subject = questionary.select(
            f"{teacher}:",
            choices=SUBJECTS,
            style=STYLE,
        ).ask()
        if subject is None:
            _err("Cancelled.")
            raise typer.Exit(0)
        teacher_subjects[teacher] = subject

    save_config({
        "api_url": api_url,
        "token": token,
        "teacher_subjects": teacher_subjects,
    })

    _section("Done")
    _ok("Config saved to config.json.")
    _info("Run [bold]adalove[/bold] and choose Fetch to generate your activity files.")
    console.print()
```

- [ ] **Step 2: Replace `setup()` body**

Replace the entire `setup()` function body (keep the decorator and docstring):

```python
@app.command()
def setup() -> None:
    """Configure API credentials and assign teachers to subjects."""
    _section("Credentials")

    api_url: str | None = None
    token: str | None = None

    _info("Attempting to auto-capture credentials from browser...")
    try:
        from adalove.browser.capture import capture_credentials
        api_url, token = capture_credentials()
        _ok("Credentials captured automatically.")
    except ImportError:
        _info("Playwright not installed — falling back to manual input.")
        _info("Install with: [bold]pip install playwright && playwright install chromium[/bold]")
    except PermissionError as e:
        _err(str(e))
        raise typer.Exit(1)
    except (TimeoutError, ValueError) as e:
        _err(f"Auto-capture failed: {e}")
        _info("Falling back to manual input.")

    if api_url is None or token is None:
        console.print()
        api_url = questionary.text(
            "Full API URL  (Network tab → request URL):",
            style=STYLE,
        ).ask()
        if not api_url:
            _err("Cancelled.")
            raise typer.Exit(0)

        token = questionary.password(
            "Authorization header value  (e.g. 'Bearer eyJ...'):",
            style=STYLE,
        ).ask()
        if not token:
            _err("Cancelled.")
            raise typer.Exit(0)

    _run_setup(api_url, token)
```

- [ ] **Step 3: Run existing test suite**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add cli/main.py
git commit -m "feat: auto-capture credentials in setup(), fall back to manual on failure"
```

---

### Task 4: Update `check()` to auto-capture on token expiry

**Files:**
- Modify: `cli/main.py`

- [ ] **Step 1: Replace the `PermissionError` branch in `check()`**

In `check()`, find the `except PermissionError:` block (currently around line 309) and replace it:

```python
    except PermissionError:
        _err("Token expired or invalid.")
        console.print()
        _info("Attempting to auto-capture new credentials...")
        console.print()
        try:
            from adalove.browser.capture import capture_credentials
            api_url, new_token = capture_credentials()
            _ok("Credentials captured. Reconfiguring...")
            console.print()
            _run_setup(api_url, new_token)
            return
        except ImportError:
            _info("Playwright not installed — falling back to manual setup.")
        except PermissionError as e:
            _err(str(e))
            raise typer.Exit(1)
        except (TimeoutError, ValueError) as e:
            _err(f"Auto-capture failed: {e}")
            _info("Falling back to manual setup.")
        console.print()
        setup()
        return
```

- [ ] **Step 2: Run full test suite**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Smoke-test the happy path manually**

```bash
adalove check
```

If the token in `config.json` is expired, the tool should open a Chromium window, navigate to Adalove, wait 8 seconds, and either reconfigure automatically or print a clear error.

- [ ] **Step 4: Commit**

```bash
git add cli/main.py
git commit -m "feat: auto-capture credentials in check() on token expiry"
```
