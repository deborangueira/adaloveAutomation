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
