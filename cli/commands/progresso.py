"""Menu "Progresso": attendance pie and grade/progress grid, drawn in the
terminal."""

import math

import questionary
import typer
from rich import box
from rich.align import Align
from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from adalove.config.settings import load_config
from adalove.models.dashboard_metrics import DashboardMetrics
from cli.auth import _call_api
from cli.ui import STYLE, _err, console


def _draw_pie(width: int, height: int, fraction: float) -> list[str]:
    """Return a list of `height` strings of length `width` forming a pie chart.

    fraction — the "present" share (0.0–1.0).  The absent slice starts at 12 o'clock
    and grows clockwise so the right side moves while the left stays static.
    Characters are ~2× taller than wide; horizontal distances are halved to compensate.
    """
    absent = 1.0 - fraction
    absent_angle = absent * 2 * math.pi

    cx = width // 2
    cy = height // 2
    r = max(1, min(width // 4, height // 2 - 1))

    lines: list[str] = []
    for row in range(height):
        chars: list[str] = []
        for col in range(width):
            dx = (col - cx) / 2.0   # halve x to correct aspect ratio
            dy = row - cy
            if math.sqrt(dx * dx + dy * dy) <= r:
                angle = math.atan2(dx, -dy) % (2 * math.pi)  # 0 = top, clockwise
                if angle < absent_angle:
                    chars.append(" ")   # absent sector
                else:
                    chars.append("█")  # present sector
            else:
                chars.append(" ")
        lines.append("".join(chars))
    return lines


def _build_grid(metrics: DashboardMetrics) -> Table:
    def cell(title: str, value: str) -> str:
        return f"[dim]{title}[/dim]\n[bold white]{value}[/bold white]"

    tbl = Table(
        box=box.SIMPLE_HEAVY,
        show_header=False,
        padding=(0, 2),
        expand=True,
    )
    tbl.add_column("left", ratio=5, justify="center")
    tbl.add_column("sep", width=1, justify="center")
    tbl.add_column("right", ratio=5, justify="center")

    tbl.add_row(
        cell("Acumulada", f"{metrics.acumulada:.2f}"),
        "│",
        cell("Até o momento", f"{metrics.ate_o_momento:.2f}"),
    )
    tbl.add_row(
        cell("Nota necessária da prova", f"{metrics.nota_necessaria:.2f}"),
        "",
        "",
    )
    tbl.add_row(
        cell("Semana atual", str(metrics.semana_atual)),
        "│",
        cell("ponderadas dessa semana", str(metrics.ponderadas_semana)),
    )
    tbl.add_row(
        cell("Auto estudos feitos", str(metrics.auto_estudos_feitos)),
        "│",
        cell("Auto estudos a fazer", str(metrics.auto_estudos_a_fazer)),
    )
    return tbl


def dashboard() -> None:
    """Render the full-terminal ASCII dashboard and wait for the user to go back."""
    try:
        config = load_config()
    except FileNotFoundError:
        _err("config.json não encontrado. Execute o Setup primeiro.")
        return

    console.print("  Conectando...")
    try:
        config, (student_status, activities, section_date) = _call_api(
            config, lambda c: c.fetch_dashboard_data()
        )
    except KeyError as e:
        _err(f"config.json não possui a chave {e}. Execute o Setup novamente.")
        return
    except (ConnectionError, ValueError) as e:
        _err(str(e))
        return

    metrics = DashboardMetrics.from_api(student_status, activities, section_date)

    w, h = console.size
    layout_h = max(h - 3, 12)
    pane_w = max(w // 2 - 4, 1)
    pane_h = max(layout_h - 2, 1)

    pie_lines = _draw_pie(pane_w, pane_h, student_status.pie_fraction)

    left_panel = Panel(
        Align(
            Group(*[Text(line, style="white") for line in pie_lines]),
            align="center",
            vertical="middle",
        ),
        title=f"[bold white]Presença  {student_status.absence_remaining_label}[/bold white]",
        border_style="cyan",
        height=layout_h,
    )
    right_panel = Panel(
        Align(_build_grid(metrics), vertical="middle"),
        border_style="cyan",
        height=layout_h,
    )

    layout = Layout()
    layout.split_row(Layout(name="left"), Layout(name="right"))
    layout["left"].update(left_panel)
    layout["right"].update(right_panel)

    console.print(layout)
    console.print()

    result = questionary.select(
        "Dashboard",
        choices=[questionary.Choice("← Voltar ao menu", value="back")],
        style=STYLE,
    ).ask()
    if result is None:
        raise typer.Exit(0)
