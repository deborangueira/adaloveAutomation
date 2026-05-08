import math
from cli.main import _draw_pie, _build_grid
from adalove.models.dashboard_metrics import DashboardMetrics
from rich.table import Table


def _mock_metrics() -> DashboardMetrics:
    return DashboardMetrics(
        acumulada=3.5,
        ate_o_momento=4.2,
        nota_necessaria=6.5,
        semana_atual=3,
        ponderadas_semana=1,
        auto_estudos_feitos=3,
        auto_estudos_a_fazer=30,
    )


def test_draw_pie_dimensions():
    lines = _draw_pie(width=40, height=16, fraction=0.92)
    assert len(lines) == 16
    assert all(len(line) == 40 for line in lines)


def test_draw_pie_full_presence():
    lines = _draw_pie(width=40, height=16, fraction=1.0)
    interior = [c for line in lines for c in line if c != " "]
    assert len(interior) > 0, "circle should contain filled cells"
    assert all(c == "█" for c in interior)


def test_draw_pie_zero_presence():
    lines = _draw_pie(width=40, height=16, fraction=0.0)
    filled = [c for line in lines for c in line if c == "█"]
    assert len(filled) == 0


def test_draw_pie_partial_has_both():
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


def test_build_grid_returns_table():
    result = _build_grid(_mock_metrics())
    assert isinstance(result, Table)


def test_build_grid_row_count():
    result = _build_grid(_mock_metrics())
    assert len(result.rows) == 4


def test_build_grid_column_count():
    result = _build_grid(_mock_metrics())
    assert len(result.columns) == 3
