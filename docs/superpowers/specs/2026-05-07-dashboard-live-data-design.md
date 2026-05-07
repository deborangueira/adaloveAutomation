# Dashboard Live Data — Design Spec
Date: 2026-05-07

## Overview

Wire real API data into the dashboard's pie chart. When the user opens the Dashboard option, the app fetches `studentStatus` from the Adalove API and renders the absence budget as a live pie chart instead of mock data.

## Scope

This spec covers only the pie chart (absence data). The right-side grid cells remain mocked for now.

## Data Layer

### `adalove/models/student_status.py` (new file)

A `StudentStatus` dataclass parsed from the `studentStatus` key in the API response.

Fields:
- `absences_percentage: float` — parsed from the string `"0.08"`
- `absences_count: int`
- `done_evaluation_result: float` — parsed from the string `"0.00"`
- `evaluation_result: float` — parsed from the string `"0.00"`

Computed properties:
- `pie_fraction: float` — `max(0.0, min(1.0, (0.2 - absences_percentage) / 0.2))` — clamped to `[0, 1]`, represents fraction of absence budget remaining
- `absence_remaining_label: str` — `f"{round((0.2 - absences_percentage) * 100)}%"` — e.g. `"12%"` for display in the Panel title

`from_api(data: dict) -> StudentStatus` class method:
- All string fields parsed with `float(data.get(key) or "0")` — null/missing fields default to `0.0`
- `absences_count` defaults to `0` if missing

### `adalove/api/client.py`

New method `fetch_student_status() -> StudentStatus`:
- Hits the same `self._api_url` endpoint as `fetch_activities()`
- Returns `StudentStatus.from_api(data["studentStatus"])` where `data` is the full response JSON
- Raises `PermissionError` on 401/403, `ConnectionError` on network errors — same pattern as `fetch_activities()`

## Dashboard Flow

`dashboard()` in `cli/main.py`:

1. Load config with `load_config()` — on `FileNotFoundError`, call `_err()` and `return`
2. Print `"  Conectando..."` (inline, not a section header)
3. Create `AdaloveClient` and call `fetch_student_status()`
4. On `PermissionError` or `ConnectionError`, call `_err()` and `return`
5. Pass `student_status.pie_fraction` to `_draw_pie`
6. Pass `student_status.absence_remaining_label` to the Panel title: `f"[bold white]Presença  {student_status.absence_remaining_label}[/bold white]"`

`MOCK` remains in `cli/main.py` — it is no longer used at runtime but stays as a reference and for tests.

## Error Handling

All errors follow the existing pattern in `fetch`:
- `_err(message)` prints to stderr with a `✗` prefix
- Function returns immediately (no exception propagates to the user)

## Testing

New `tests/test_student_status.py`:

- `test_from_api_parses_normal_values` — string fields correctly converted to float
- `test_from_api_null_fields_default_to_zero` — null/missing fields produce `0.0`
- `test_pie_fraction_normal` — `absences_percentage=0.08` → `pie_fraction=0.6`
- `test_pie_fraction_clamped_above_max` — `absences_percentage=0.25` (>0.2) → `pie_fraction=0.0`
- `test_pie_fraction_no_absences` — `absences_percentage=0.0` → `pie_fraction=1.0`
- `test_absence_remaining_label` — `absences_percentage=0.08` → `"12%"`

## Constraints

- No new dependencies
- `fetch_student_status()` makes one HTTP request — same endpoint as `fetch_activities()`
- `MOCK` is not deleted
- Right-side grid data remains mocked
