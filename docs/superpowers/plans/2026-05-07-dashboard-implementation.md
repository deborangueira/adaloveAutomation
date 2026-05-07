# Dashboard ASCII UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Dashboard" menu option that renders a full-terminal ASCII pie-chart + data-grid using `rich`, scaled to the current terminal size, with mock data.

**Architecture:** All code lives in `cli/main.py`. A module-level `MOCK` dict holds placeholder values. Two helper functions (`_draw_pie`, `_build_grid`) are independently testable. The `dashboard()` function wires them together via `rich.layout.Layout` and exits via a `questionary` prompt.

**Tech Stack:** Python 3.11+, `rich` (Layout, Panel, Table, Text, Group, Align, box), `questionary`, `math` (stdlib)

---

## File Map

| File | Change |
|------|--------|
| `cli/main.py` | Add `import math`, `from rich.layout import Layout`, `from rich.group import Group`, `from rich import box`; add `MOCK` constant; add `_draw_pie()`, `_build_grid()`, `dashboard()`; extend main menu |
| `tests/test_dashboard.py` | New file — unit tests for `_draw_pie` and `_build_grid` |

---

### Task 1: Add imports and MOCK constant

**Files:**
- Modify: `cli/main.py:1-10`

- [ ] **Step 1: Add missing imports to `cli/main.py`**

Open `cli/main.py`. After the existing `import` block (after line 9, `from rich.text import Text`), add:

```python
import math

from rich import box
from rich.group import Group
from rich.layout import Layout
```

- [ ] **Step 2: Add the MOCK constant after the `console` definitions (after line 26)**

```python
MOCK: dict[str, float | int] = {
    "presenca": 0.92,
    "acumulada": 0.0,
    "ate_o_momento": 0.0,
    "nota_necessaria": 0.0,
    "semana_atual": 3,
    "ponderadas_semana": 5,
    "auto_estudos_feitos": 0.0,
    "auto_estudos_a_fazer": 0.0,
}
```

- [ ] **Step 3: Verify the file still imports cleanly**

```bash
cd /home/rafa/Work/personalProjects/adaloveAutomation
python -c "from cli.main import MOCK; print(MOCK)"
```

Expected output:
```
{'presenca': 0.92, 'acumulada': 0.0, 'ate_o_momento': 0.0, 'nota_necessaria': 0.0, 'semana_atual': 3, 'ponderadas_semana': 5, 'auto_estudos_feitos': 0.0, 'auto_estudos_a_fazer': 0.0}
```

- [ ] **Step 4: Commit**

```bash
git add cli/main.py
git commit -m "feat(dashboard): add imports and MOCK data constant"
```

---

### Task 2: Implement `_draw_pie()` with tests

**Files:**
- Modify: `cli/main.py` (add `_draw_pie` before the `# ── main menu` comment)
- Create: `tests/test_dashboard.py`

- [ ] **Step 1: Write the failing tests in `tests/test_dashboard.py`**

```python
import math
from cli.main import _draw_pie


def test_draw_pie_dimensions():
    lines = _draw_pie(width=40, height=16, fraction=0.92)
    assert len(lines) == 16
    assert all(len(line) == 40 for line in lines)


def test_draw_pie_full_presence():
    # fraction=1.0 → no absent sector → every interior cell is '█'
    lines = _draw_pie(width=40, height=16, fraction=1.0)
    interior = [c for line in lines for c in line if c != " "]
    assert len(interior) > 0, "circle should contain filled cells"
    assert all(c == "█" for c in interior)


def test_draw_pie_zero_presence():
    # fraction=0.0 → entire circle is absent → no '█' cells at all
    lines = _draw_pie(width=40, height=16, fraction=0.0)
    filled = [c for line in lines for c in line if c == "█"]
    assert len(filled) == 0


def test_draw_pie_partial_has_both():
    # fraction=0.5 → roughly half filled, half empty inside the circle
    lines = _draw_pie(width=40, height=16, fraction=0.5)
    filled = [c for line in lines for c in line if c == "█"]
    empty_interior = []
    cx, cy = 20, 8
    r = min(40 // 4, 16 // 2 - 2)
    for row_idx, line in enumerate(lines):
        for col_idx, c in enumerate(line):
            dx = (col_idx - cx) / 2.0
            dy = row_idx - cy
            if math.sqrt(dx * dx + dy * dy) <= r and c == " ":
                empty_interior.append(c)
    assert len(filled) > 0
    assert len(empty_interior) > 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /home/rafa/Work/personalProjects/adaloveAutomation
python -m pytest tests/test_dashboard.py -v 2>&1 | head -30
```

Expected: `ImportError` or `AttributeError` — `_draw_pie` not yet defined.

- [ ] **Step 3: Add `_draw_pie` to `cli/main.py`**

Add this function directly before the `# ── main menu ──` comment block:

```python
# ── dashboard helpers ─────────────────────────────────────────────────────────

def _draw_pie(width: int, height: int, fraction: float) -> list[str]:
    """Return a list of `height` strings of length `width` forming a pie chart.

    fraction — the "present" share (0.0–1.0).  The absent slice sits at 12 o'clock.
    Characters are ~2× taller than wide; horizontal distances are halved to compensate.
    """
    absent = 1.0 - fraction
    absent_angle = absent * 2 * math.pi

    cx = width // 2
    cy = height // 2
    r = min(width // 4, height // 2 - 2)

    lines: list[str] = []
    for row in range(height):
        chars: list[str] = []
        for col in range(width):
            dx = (col - cx) / 2.0   # halve x to correct aspect ratio
            dy = row - cy
            if math.sqrt(dx * dx + dy * dy) <= r:
                angle = math.atan2(dx, -dy) % (2 * math.pi)  # 0 = top, clockwise
                half = absent_angle / 2
                if angle <= half or angle >= 2 * math.pi - half:
                    chars.append(" ")   # absent sector
                else:
                    chars.append("█")  # present sector
            else:
                chars.append(" ")
        lines.append("".join(chars))
    return lines
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /home/rafa/Work/personalProjects/adaloveAutomation
python -m pytest tests/test_dashboard.py -v
```

Expected: 4 tests, all PASSED.

- [ ] **Step 5: Commit**

```bash
git add cli/main.py tests/test_dashboard.py
git commit -m "feat(dashboard): add _draw_pie ASCII renderer with tests"
```

---

### Task 3: Implement `_build_grid()` with tests

**Files:**
- Modify: `cli/main.py` (add `_build_grid` after `_draw_pie`)
- Modify: `tests/test_dashboard.py` (append new tests)

- [ ] **Step 1: Append failing tests to `tests/test_dashboard.py`**

```python
from rich.table import Table
from cli.main import _build_grid, MOCK


def test_build_grid_returns_table():
    result = _build_grid(MOCK)
    assert isinstance(result, Table)


def test_build_grid_row_count():
    result = _build_grid(MOCK)
    assert len(result.rows) == 4


def test_build_grid_column_count():
    result = _build_grid(MOCK)
    # 3 columns: left, sep, right
    assert len(result.columns) == 3
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /home/rafa/Work/personalProjects/adaloveAutomation
python -m pytest tests/test_dashboard.py::test_build_grid_returns_table -v
```

Expected: `ImportError` — `_build_grid` not yet defined.

- [ ] **Step 3: Add `_build_grid` to `cli/main.py`** (after `_draw_pie`, still inside the `# ── dashboard helpers` section)

```python
def _build_grid(data: dict) -> "Table":
    """Build the right-pane data grid from a data dict."""
    from rich.table import Table  # already available via rich

    def cell(title: str, value: str) -> str:
        return f"[dim]{title}[/dim]\n[bold white]{value}[/bold white]"

    tbl = Table(
        box=box.HORIZONTALS,
        show_header=False,
        padding=(1, 2),
        expand=True,
    )
    tbl.add_column("left", ratio=5, justify="center")
    tbl.add_column("sep", width=1, justify="center")
    tbl.add_column("right", ratio=5, justify="center")

    # Row 1 — two columns
    tbl.add_row(
        cell("Acumulada", str(data["acumulada"])),
        "│",
        cell("Até o momento", str(data["ate_o_momento"])),
    )
    # Row 2 — full width (right cells left empty)
    tbl.add_row(
        cell("Nota necessária da prova", str(data["nota_necessaria"])),
        "",
        "",
    )
    # Row 3 — two columns
    tbl.add_row(
        cell("Semana atual", str(data["semana_atual"])),
        "│",
        cell("ponderadas dessa semana", str(data["ponderadas_semana"])),
    )
    # Row 4 — two columns
    tbl.add_row(
        cell("Auto estudos feitos", str(data["auto_estudos_feitos"])),
        "│",
        cell("Auto estudos a fazer", str(data["auto_estudos_a_fazer"])),
    )
    return tbl
```

- [ ] **Step 4: Run all dashboard tests**

```bash
cd /home/rafa/Work/personalProjects/adaloveAutomation
python -m pytest tests/test_dashboard.py -v
```

Expected: 7 tests, all PASSED.

- [ ] **Step 5: Commit**

```bash
git add cli/main.py tests/test_dashboard.py
git commit -m "feat(dashboard): add _build_grid data table with tests"
```

---

### Task 4: Implement `dashboard()` and wire into menu

**Files:**
- Modify: `cli/main.py` (add `dashboard()` function and update main menu)

- [ ] **Step 1: Add `dashboard()` function to `cli/main.py`**

Add after `_build_grid`, still inside the `# ── dashboard helpers` section:

```python
def dashboard() -> None:
    """Render the full-terminal ASCII dashboard and wait for the user to go back."""
    _header("Dashboard")

    data = dict(MOCK)
    w, h = console.size
    layout_h = max(h - 6, 12)
    pane_w = w // 2 - 4
    pane_h = layout_h - 4

    absent_pct = f"{round((1 - data['presenca']) * 100)}%"
    pie_lines = _draw_pie(pane_w, pane_h, float(data["presenca"]))

    pie_group = Group(
        Align(Text("Presença", style="bold white"), align="center"),
        Text(""),
        *[Text(line, style="dim white") for line in pie_lines],
        Text(""),
        Align(Text(absent_pct, style="white"), align="center"),
    )
    left_panel = Panel(pie_group, border_style="cyan", height=layout_h)
    right_panel = Panel(
        Align(_build_grid(data), vertical="middle"),
        border_style="cyan",
        height=layout_h,
    )

    layout = Layout()
    layout.split_row(Layout(name="left"), Layout(name="right"))
    layout["left"].update(left_panel)
    layout["right"].update(right_panel)

    console.print(layout)
    console.print()

    questionary.select(
        "Dashboard",
        choices=[questionary.Choice("← Back to menu", value="back")],
        style=STYLE,
    ).ask()
```

- [ ] **Step 2: Add "Dashboard" to the main menu choices**

In `cli/main.py`, locate the `questionary.select` call in `main()`. Add the new choice between "Fetch" and "Exit":

```python
choices=[
    questionary.Choice("  Setup      —  Configure credentials & teacher mapping", value="setup"),
    questionary.Choice("  Fetch      —  Download and filter activities",           value="fetch"),
    questionary.Choice("  Dashboard  —  View your progress summary",               value="dashboard"),
    questionary.Choice("  Exit",                                                    value="exit"),
],
```

- [ ] **Step 3: Add the `dashboard` branch to the menu handler**

Locate the `if/elif` block that handles `choice` in `main()` and add:

```python
elif choice == "dashboard":
    dashboard()
```

- [ ] **Step 4: Run the full test suite to check for regressions**

```bash
cd /home/rafa/Work/personalProjects/adaloveAutomation
python -m pytest -v
```

Expected: all existing tests PASSED, 7 dashboard tests PASSED, no failures.

- [ ] **Step 5: Smoke-test the import**

```bash
python -c "from cli.main import dashboard, _draw_pie, _build_grid; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add cli/main.py
git commit -m "feat(dashboard): add dashboard() and wire into main menu"
```
