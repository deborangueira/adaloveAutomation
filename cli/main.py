import math
from pathlib import Path

import questionary
import typer
from questionary import Style
from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from adalove.api.client import AdaloveClient
from adalove.config.settings import load_config, save_config
from adalove.config.subjects import SUBJECTS
from adalove.filters.activity import filter_activities, get_unique_teachers, get_unique_weeks
from adalove.output.links import append_links_md, write_links_md
from adalove.output.markdown import append_activities_md, write_activities_md
from adalove.output.state import load_written_uuids, save_written_uuids

app = typer.Typer(
    help="Fetch and filter Adalove activities.",
    add_completion=False,
    invoke_without_command=True,
)
console = Console()
err_console = Console(stderr=True)

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

BANNER = """\
 █████╗ ██████╗  █████╗ ██╗      ██████╗ ██╗   ██╗███████╗
██╔══██╗██╔══██╗██╔══██╗██║     ██╔═══██╗██║   ██║██╔════╝
███████║██║  ██║███████║██║     ██║   ██║██║   ██║█████╗
██╔══██║██║  ██║██╔══██║██║     ██║   ██║╚██╗ ██╔╝██╔══╝
██║  ██║██████╔╝██║  ██║███████╗╚██████╔╝ ╚████╔╝ ███████╗
╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝   ╚═══╝  ╚══════╝"""

# Shared style for every questionary prompt in the app
STYLE = Style([
    ("qmark",       "fg:#5fd7ff bold"),
    ("question",    "bold white"),
    ("answer",      "fg:#5fd7ff bold"),
    ("pointer",     "fg:#5fd7ff bold"),
    ("highlighted", "fg:#5fd7ff bold"),
    ("selected",    "fg:#5fd7ff"),
    ("separator",   "fg:#444466"),
    ("instruction", "fg:#444466 italic"),
    ("text",        "white"),
    ("disabled",    "fg:#444466 italic"),
])


# ── visual helpers ────────────────────────────────────────────────────────────

def _header(subtitle: str) -> None:
    console.print()
    console.print(Align(BANNER, align="center"), style="bold cyan")
    console.print(Align(f"[dim]{subtitle}[/dim]", align="center"))
    console.print()


def _window(title: str, body: str = "") -> None:
    """Print a framed panel — used above interactive prompts."""
    content = Text.from_markup(body) if body else Text("")
    console.print(
        Panel(
            content,
            title=f"[bold cyan]{title}[/bold cyan]",
            border_style="cyan",
            padding=(0, 2),
        )
    )


def _section(title: str) -> None:
    console.print()
    console.print(Rule(f"[bold white]{title}[/bold white]", style="cyan"))
    console.print()


def _ok(msg: str) -> None:
    console.print(f"  [bold green]✓[/bold green]  {msg}")


def _err(msg: str) -> None:
    err_console.print(f"  [bold red]✗[/bold red]  {msg}")


def _info(msg: str) -> None:
    console.print(f"  [dim]•[/dim]  {msg}")


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
    r = max(1, min(width // 4, height // 2 - 1))

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


def _build_grid(data: dict) -> Table:
    """Build the right-pane data grid from a data dict."""
    def cell(title: str, value: str) -> str:
        return f"[dim]{title}[/dim]\n[bold white]{value}[/bold white]"

    tbl = Table(
        box=box.SIMPLE_HEAVY,
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


def dashboard() -> None:
    """Render the full-terminal ASCII dashboard and wait for the user to go back."""
    data = dict(MOCK)
    w, h = console.size
    layout_h = max(h - 3, 12)
    pane_w = max(w // 2 - 4, 1)
    pane_h = max(layout_h - 2, 1)  # full panel inner height

    presenca_pct = f"{round(float(data['presenca']) * 100)}%"
    pie_lines = _draw_pie(pane_w, pane_h, float(data["presenca"]))

    left_panel = Panel(
        Align(
            Group(*[Text(line, style="white") for line in pie_lines]),
            align="center",
            vertical="middle",
        ),
        title=f"[bold white]Presença  {presenca_pct}[/bold white]",
        border_style="cyan",
        height=layout_h,
    )
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

    result = questionary.select(
        "Dashboard",
        choices=[questionary.Choice("← Back to menu", value="back")],
        style=STYLE,
    ).ask()
    if result is None:
        raise typer.Exit(0)


# ── main menu ─────────────────────────────────────────────────────────────────

@app.callback()
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return

    _header("Activity Manager")

    _window(
        "Main Menu",
        "[dim]↑ ↓  navigate    Enter  confirm[/dim]",
    )
    console.print()

    choice = questionary.select(
        "Choose an option:",
        choices=[
            questionary.Choice("  Setup      —  Configure credentials & teacher mapping", value="setup"),
            questionary.Choice("  Fetch      —  Download and filter activities",           value="fetch"),
            questionary.Choice("  Dashboard  —  View your progress summary",               value="dashboard"),
            questionary.Choice("  Exit",                                                    value="exit"),
        ],
        style=STYLE,
    ).ask()

    if choice is None or choice == "exit":
        raise typer.Exit(0)

    if choice == "setup":
        check(ctx)
    elif choice == "fetch":
        ctx.invoke(fetch)
    elif choice == "dashboard":
        dashboard()


# ── check ─────────────────────────────────────────────────────────────────────

@app.command()
def check(ctx: typer.Context) -> None:
    """Verify the current setup is still working."""
    _section("Checking Setup")

    try:
        config = load_config()
    except FileNotFoundError:
        _err("No config.json found.")
        console.print()
        _info("Redirecting to Setup...")
        console.print()
        setup()
        return

    console.print("  Connecting to API...")
    try:
        client = AdaloveClient(api_url=config["api_url"], token=config["token"])
        activities = client.fetch_activities()
    except KeyError as e:
        _err(f"config.json is missing key {e}.")
        console.print()
        _info("Redirecting to Setup...")
        console.print()
        setup()
        return
    except PermissionError:
        _err("Token expired or invalid.")
        console.print()
        _info("Redirecting to Setup...")
        console.print()
        setup()
        return
    except (ConnectionError, ValueError) as e:
        _err(str(e))
        console.print()
        raise typer.Exit(1)

    _ok(f"Setup atual ainda funciona.  [dim]({len(activities)} activities reachable)[/dim]")
    console.print()

    reconfigure = questionary.confirm(
        "Deseja reconfigurar mesmo assim?",
        default=False,
        style=STYLE,
    ).ask()

    if reconfigure:
        setup()


# ── setup ─────────────────────────────────────────────────────────────────────

@app.command()
def setup() -> None:
    """Configure API credentials and assign teachers to subjects."""
    _section("Credentials")

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


# ── fetch ─────────────────────────────────────────────────────────────────────

@app.command()
def fetch() -> None:
    """Interactively filter activities and write output markdown files."""
    _section("Loading")

    try:
        config = load_config()
    except FileNotFoundError as e:
        _err(str(e))
        raise typer.Exit(1)

    teacher_subjects: dict[str, str] = config.get("teacher_subjects", {})

    console.print("  Fetching activities...")
    try:
        client = AdaloveClient(api_url=config["api_url"], token=config["token"])
        activities = client.fetch_activities()
    except KeyError as e:
        _err(f"config.json is missing key {e}. Run setup again.")
        raise typer.Exit(1)
    except PermissionError as e:
        _err(str(e))
        raise typer.Exit(1)
    except (ConnectionError, ValueError) as e:
        _err(str(e))
        raise typer.Exit(1)

    _ok(f"{len(activities)} activities loaded.")

    _section("Filters")

    _window("Weeks", "[dim]Space  toggle    Enter  confirm[/dim]")
    console.print()

    week_choices = [
        questionary.Choice(title=caption, value=num)
        for num, caption in get_unique_weeks(activities)
    ]
    while True:
        selected_week_nums = questionary.checkbox(
            "Select weeks:",
            choices=week_choices,
            style=STYLE,
        ).ask()
        if selected_week_nums is None:
            _err("Cancelled.")
            raise typer.Exit(0)
        if selected_week_nums:
            break
        console.print("  [yellow]Select at least one week.[/yellow]")

    console.print()
    _window("Subjects", "[dim]Space  toggle    Enter  confirm[/dim]")
    console.print()

    subject_choices = [s for s in SUBJECTS if s != "Não presente no módulo"]
    while True:
        selected_subjects = questionary.checkbox(
            "Select subjects:",
            choices=subject_choices,
            style=STYLE,
        ).ask()
        if selected_subjects is None:
            _err("Cancelled.")
            raise typer.Exit(0)
        if selected_subjects:
            break
        console.print("  [yellow]Select at least one subject.[/yellow]")

    filtered = filter_activities(
        activities=activities,
        weeks=selected_week_nums,
        subjects=selected_subjects,
        teacher_subjects=teacher_subjects,
    )

    _section("Results")

    if not filtered:
        _info("No activities match the selected filters.")
        console.print()
        raise typer.Exit(0)

    written_uuids = load_written_uuids()
    new_activities = [a for a in filtered if a.uuid not in written_uuids]
    already_count = len(filtered) - len(new_activities)

    _info(
        f"{len(filtered)} matched  •  "
        f"[green]{len(new_activities)} new[/green]  •  "
        f"[dim]{already_count} already written[/dim]"
    )

    if not new_activities:
        _ok("Nothing new to add — files are up to date.")
        console.print()
        raise typer.Exit(0)

    files_exist = (Path.cwd() / "output" / "activities.md").exists()

    if files_exist:
        activities_path = append_activities_md(new_activities, teacher_subjects)
        links_path = append_links_md(new_activities, teacher_subjects)
    else:
        activities_path = write_activities_md(
            new_activities, teacher_subjects, selected_week_nums, selected_subjects
        )
        links_path = write_links_md(
            new_activities, teacher_subjects, selected_week_nums, selected_subjects
        )

    updated_uuids = written_uuids | {a.uuid for a in new_activities}
    save_written_uuids(updated_uuids)

    _ok(f"[bold]{activities_path}[/bold]  [dim](+{len(new_activities)})[/dim]")
    _ok(f"[bold]{links_path}[/bold]  [dim](+{len([a for a in new_activities if a.url])} links)[/dim]")
    console.print()


if __name__ == "__main__":
    app()
