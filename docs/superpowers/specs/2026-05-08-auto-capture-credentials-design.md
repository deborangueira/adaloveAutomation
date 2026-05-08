# Auto-Capture Credentials via Browser — Design Spec

**Date:** 2026-05-08
**Status:** Approved

## Problem

The Adalove Bearer token is a short-lived AWS Cognito JWT (~1h). Every time it expires, `check` fails and the user must manually open Chrome DevTools, find the network request, and copy the URL + Authorization header into the CLI. This friction repeats every session.

## Goal

When `setup` runs — or when `check` detects an expired/invalid token — automatically capture the API URL and Bearer token from the Adalove site via a Playwright-managed browser, with no manual copy-paste.

## Approach

Playwright with a persistent Chromium profile (`~/.adalove-browser/`). The user logs in once in that browser; subsequent runs reuse the saved session. Playwright intercepts network requests to `apiv2.inteli.edu.br/sections/*/userdata`, collects all matching responses within 8 seconds, and picks the one with the largest response body (always the correct one when multiple fire).

## Architecture

### New module: `adalove/browser/capture.py`

Single public function:

```python
def capture_credentials() -> tuple[str, str]:
    """Returns (api_url, token). Raises PermissionError, TimeoutError, or ValueError."""
```

**Steps inside `capture_credentials()`:**

1. Launch a persistent Chromium context at `~/.adalove-browser/` (non-headless)
2. Register a response listener for URLs matching `apiv2.inteli.edu.br/sections/*/userdata`
3. Navigate to `https://adalove.inteli.edu.br/`
4. If the page URL contains the Cognito login domain → raise `PermissionError`
5. Click the correct sidebar item (Atividades) to guarantee the request fires even if already on the page
6. Collect all matching responses for up to 8 seconds
7. Pick the response with the largest body
8. Return `(response.url, request.headers["authorization"])` and close the context

### Modified: `cli/main.py`

Extract a private helper `_run_setup(api_url: str, token: str) -> None` that contains the existing validation + teacher-mapping logic (everything in `setup()` after the manual prompts). Both `setup()` and `check()` call this helper once they have credentials.

**`setup()`:** Try `capture_credentials()` first. On success, call `_run_setup(api_url, token)`. On any capture error, show a message and fall back to the existing manual prompts, then call `_run_setup(api_url, token)`.

**`check()`:** On `PermissionError` (expired token), try `capture_credentials()` before redirecting to manual `setup()`. If capture succeeds, call `_run_setup(api_url, token)` directly (skips prompts entirely). If capture fails, call `setup()` as before.

### Modified: `requirements.txt`

Add `playwright>=1.40`. Import is guarded in `capture.py` so the tool degrades gracefully to manual prompts if Playwright is not installed. First-run error instructs the user to run `playwright install chromium`.

## Error Handling

| Situation | Behaviour |
|---|---|
| Redirected to Cognito login | `PermissionError` → "Not logged in — open Chrome and log into Adalove first, then re-run setup." No fallback to manual. |
| 8s timeout, no matching request | `TimeoutError` → message shown, falls back to manual prompts |
| `playwright` not installed | `ImportError` caught → skip auto-capture, go straight to manual prompts |
| `authorization` header missing | `ValueError` → same fallback as timeout |

## Files Changed

| File | Change |
|---|---|
| `adalove/browser/__init__.py` | New (empty) |
| `adalove/browser/capture.py` | New — `capture_credentials()` |
| `cli/main.py` | Modified — `setup()` and `check()` |
| `requirements.txt` | Add `playwright>=1.40` |

## Out of Scope

- Handling the Cognito login flow automatically (user must be logged in)
- Changes to `AdaloveClient`, `config.json` format, or any other module
- Cross-browser support (Chromium only)
