# Dashboard ASCII UI — Design Spec
Date: 2026-05-07

## Overview

Add a "Dashboard" option to the existing main menu that renders a full-terminal ASCII dashboard using `rich`. The dashboard displays mocked student progress data (attendance, grades, weekly stats) in a two-column layout with a pie chart on the left and a data grid on the right. Data is mocked now; live API integration is deferred.

## Menu Integration

A new `questionary.Choice` is added to the main menu in `cli/main.py` between "Fetch" and "Exit":

```
  Dashboard  —  View your progress summary
```

Selecting it calls a new `dashboard()` function defined in `cli/main.py`.

## Layout

Uses `rich.layout.Layout` to split the terminal horizontally into two equal halves:

- `layout["left"]` — pie chart
- `layout["right"]` — data grid

Both halves are rendered inside `rich.Panel` with `border_style="cyan"` to match the existing UI style. The outer layout height is `console.size.height - 6` to reserve space for the header and the bottom prompt.

## Pie Chart (left pane)

A pure-Python ASCII renderer built inside the `dashboard()` function:

1. Read `console.size` to get available width and height for the left pane.
2. Compute a radius: `r = min(width // 4, height // 2 - 2)`, adjusted for the ~2:1 character aspect ratio (characters are taller than wide).
3. For each character cell `(row, col)` in the drawing area, check if the cell falls inside the circle and compute its angle relative to the center.
4. The "present" sector spans ~352° (starting from the top, clockwise); the "absent" sector spans ~8°.
5. Fill "present" cells with `█` in `dim white`; absent sector cells are left as spaces (dark background shows through).
6. Draw the two spoke boundary lines of the absent sector explicitly using `╱` / `╲` or `│` characters.
7. Render "Presença" in `bold white` centered above the circle.
8. Render "8%" in `white` centered below the circle.

The entire drawing is assembled as a list of strings and passed to the left Layout pane as a `rich.Text` object.

## Data Grid (right pane)

A `rich.table.Table` with `box=rich.box.SIMPLE_HEAVY` (horizontal row dividers, no outer border conflicting with the Panel). The table has three columns: `left_val`, `sep`, `right_val` — where `sep` is a fixed-width column containing `│` to produce the vertical divider for two-column rows.

Row layout:

| Row | Left cell | Right cell |
|-----|-----------|------------|
| 1 | Acumulada / `0.0` | Até o momento / `0.0` |
| 2 | *(spans full width)* Nota necessária da prova / `0.0` | — |
| 3 | Semana atual / `3` | ponderadas dessa semana / `5` |
| 4 | Auto estudos feitos / `0.0` | Auto estudos a fazer / `0.0` |

Each cell displays the title in `dim` on one line and the value in `bold white` centered below it. Row 2 spans the full width using `end_section=True` and a colspan-equivalent approach (merging left and right columns for that row).

## Mock Data

A plain dict at the top of `dashboard()`:

```python
MOCK = {
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

The pie chart absent slice angle is derived from `1 - MOCK["presenca"]`.

## Exit

After rendering the dashboard with `console.print(layout)`, a `questionary.select` prompt with a single "← Back to menu" choice is shown. Selecting it returns control to the main menu callback.

## Constraints

- No new files — all code added to `cli/main.py`.
- No new dependencies — `rich` is already installed.
- No live resize — dashboard renders once at the terminal size at the moment it is opened.
- The existing menu, setup, fetch, and check flows are not modified.
