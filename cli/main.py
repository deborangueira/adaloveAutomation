import sys
import math
from pathlib import Path

# When the venv python binary is a symlink to the system interpreter, venv
# detection can fail and site-packages won't include the venv's packages.
# Add them explicitly so optional deps like playwright are always found.
_venv_lib = Path(__file__).resolve().parent.parent / ".venv" / "lib"
if _venv_lib.is_dir():
    for _d in _venv_lib.iterdir():
        _sp = _d / "site-packages"
        if _sp.is_dir() and str(_sp) not in sys.path:
            sys.path.insert(1, str(_sp))

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
from adalove.models.dashboard_metrics import DashboardMetrics
from adalove.config.subjects import SUBJECTS
from adalove.filters.activity import filter_activities, get_unique_teachers, get_unique_weeks
from adalove.writers.links import append_links_md, write_links_md
from adalove.writers.markdown import append_activities_md, write_activities_md
from adalove.writers.state import load_written_uuids, save_written_uuids

app = typer.Typer(
    help="Fetch and filter Adalove activities.",
    add_completion=False,
    invoke_without_command=True,
)
console = Console()
err_console = Console(stderr=True)

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
        client = AdaloveClient(api_url=config["api_url"], token=config["token"])
        student_status, activities, section_date = client.fetch_dashboard_data()
    except KeyError as e:
        _err(f"config.json não possui a chave {e}. Execute o Setup novamente.")
        return
    except PermissionError as e:
        _err(str(e))
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


# ── main menu ─────────────────────────────────────────────────────────────────

@app.callback()
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return

    _header("Gerenciador de Atividades")

    _window(
        "Menu Principal",
        "[dim]↑ ↓  navegar    Enter  confirmar[/dim]",
    )
    console.print()

    choice = questionary.select(
        "Escolha uma opção:",
        choices=[
            questionary.Choice("  Setup      —  Configurar credenciais e mapeamento de professores", value="setup"),
            questionary.Choice("  Buscar     —  Baixar e filtrar atividades",                        value="fetch"),
            questionary.Choice("  Dashboard  —  Ver resumo do seu progresso",                        value="dashboard"),
            questionary.Choice("  Sair",                                                              value="exit"),
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
    """Verifica se a configuração atual ainda está funcionando."""
    _section("Verificando Configuração")

    try:
        config = load_config()
    except FileNotFoundError:
        _err("config.json não encontrado.")
        console.print()
        _info("Redirecionando para o Setup...")
        console.print()
        setup()
        return

    console.print("  Conectando à API...")
    try:
        client = AdaloveClient(api_url=config["api_url"], token=config["token"])
        activities = client.fetch_activities()
    except KeyError as e:
        _err(f"config.json não possui a chave {e}.")
        console.print()
        _info("Redirecionando para o Setup...")
        console.print()
        setup()
        return
    except PermissionError:
        _err("Token expirado ou inválido.")
        console.print()
        _info("Tentando capturar novas credenciais automaticamente...")
        console.print()
        try:
            from adalove.browser.capture import capture_credentials
            api_url, new_token = capture_credentials()
            _ok("Credenciais capturadas. Reconfigurando...")
            console.print()
            _run_setup(api_url, new_token)
            return
        except ImportError:
            _info("Playwright não instalado — voltando para configuração manual.")
        except PermissionError as e:
            _err(str(e))
            raise typer.Exit(1)
        except (TimeoutError, ValueError) as e:
            _err(f"Captura automática falhou: {e}")
            _info("Voltando para configuração manual.")
        console.print()
        _section("Credenciais")
        api_url, token = _prompt_credentials()
        _run_setup(api_url, token)
        return
    except (ConnectionError, ValueError) as e:
        _err(str(e))
        console.print()
        raise typer.Exit(1)

    _ok(f"Configuração atual ainda funciona.  [dim]({len(activities)} atividades acessíveis)[/dim]")
    console.print()

    reconfigure = questionary.confirm(
        "Deseja reconfigurar mesmo assim?",
        default=False,
        style=STYLE,
    ).ask()

    if reconfigure:
        setup()


# ── setup ─────────────────────────────────────────────────────────────────────

def _prompt_credentials() -> tuple[str, str]:
    """Prompt user to manually paste API URL and token. Returns (api_url, token)."""
    api_url = questionary.text(
        "URL completa da API  (aba Rede → URL da requisição):",
        style=STYLE,
    ).ask()
    if not api_url:
        _err("Cancelado.")
        raise typer.Exit(0)

    token = questionary.password(
        "Valor do cabeçalho Authorization  (ex: 'Bearer eyJ...'):",
        style=STYLE,
    ).ask()
    if not token:
        _err("Cancelado.")
        raise typer.Exit(0)

    return api_url, token


def _run_setup(api_url: str, token: str) -> None:
    """Validate credentials and configure teacher mapping. Saves config on success."""
    token = token.strip()
    if not token.isascii():
        bad = [c for c in token if not c.isascii()]
        _err(
            f"Token contém caracteres não-ASCII {bad}.\n"
            "     No devtools, clique com o botão direito no valor de Authorization → Copiar Valor."
        )
        raise typer.Exit(1)

    console.print()
    console.print("  Validando credenciais...")
    try:
        client = AdaloveClient(api_url=api_url, token=token)
        activities = client.fetch_activities()
    except PermissionError as e:
        _err(str(e))
        raise typer.Exit(1)
    except (ConnectionError, ValueError) as e:
        _err(str(e))
        raise typer.Exit(1)

    _ok(f"{len(activities)} atividades encontradas.")

    teachers = get_unique_teachers(activities)
    if not teachers:
        _err("Nenhum professor encontrado na resposta. Verifique a URL da API.")
        raise typer.Exit(1)

    _section("Mapeamento de Professores")

    teacher_subjects: dict[str, str] = {}

    try:
        existing = load_config()
        existing_map: dict[str, str] = existing.get("teacher_subjects", {})
    except FileNotFoundError:
        existing_map = {}

    if existing_map:
        for teacher, subject in existing_map.items():
            _info(f"  {teacher} → {subject}")
        console.print()
        keep = questionary.confirm(
            "Manter o mapeamento de professores existente?",
            default=True,
            style=STYLE,
        ).ask()
        if keep is None:
            _err("Cancelado.")
            raise typer.Exit(0)
        if keep:
            teacher_subjects = existing_map
        else:
            for teacher in teachers:
                subject = questionary.select(
                    f"{teacher}:",
                    choices=SUBJECTS,
                    style=STYLE,
                ).ask()
                if subject is None:
                    _err("Cancelado.")
                    raise typer.Exit(0)
                teacher_subjects[teacher] = subject
    else:
        for teacher in teachers:
            subject = questionary.select(
                f"{teacher}:",
                choices=SUBJECTS,
                style=STYLE,
            ).ask()
            if subject is None:
                _err("Cancelado.")
                raise typer.Exit(0)
            teacher_subjects[teacher] = subject

    save_config({
        "api_url": api_url,
        "token": token,
        "teacher_subjects": teacher_subjects,
    })

    _section("Concluído")
    _ok("Configuração salva em config.json.")
    _info("Execute [bold]adalove[/bold] e escolha Buscar para gerar seus arquivos de atividades.")
    console.print()


@app.command()
def setup() -> None:
    """Configura credenciais da API e mapeia professores às disciplinas."""
    _section("Credenciais")

    api_url: str | None = None
    token: str | None = None

    _info("Tentando capturar credenciais automaticamente pelo navegador...")
    try:
        from adalove.browser.capture import capture_credentials
        api_url, token = capture_credentials()
        _ok("Credenciais capturadas automaticamente.")
    except ImportError:
        _info("Playwright não instalado — usando entrada manual.")
        _info("Instale com: [bold]pip install playwright && playwright install chromium[/bold]")
    except PermissionError as e:
        _err(str(e))
        raise typer.Exit(1)
    except (TimeoutError, ValueError) as e:
        _err(f"Captura automática falhou: {e}")
        _info("Usando entrada manual.")

    if api_url is None or token is None:
        console.print()
        api_url, token = _prompt_credentials()

    _run_setup(api_url, token)


# ── fetch ─────────────────────────────────────────────────────────────────────

@app.command()
def fetch() -> None:
    """Filtra atividades interativamente e gera os arquivos markdown de saída."""
    _section("Carregando")

    try:
        config = load_config()
    except FileNotFoundError as e:
        _err(str(e))
        raise typer.Exit(1)

    teacher_subjects: dict[str, str] = config.get("teacher_subjects", {})

    console.print("  Buscando atividades...")
    try:
        client = AdaloveClient(api_url=config["api_url"], token=config["token"])
        activities = client.fetch_activities()
    except KeyError as e:
        _err(f"config.json não possui a chave {e}. Execute o setup novamente.")
        raise typer.Exit(1)
    except PermissionError as e:
        _err(str(e))
        raise typer.Exit(1)
    except (ConnectionError, ValueError) as e:
        _err(str(e))
        raise typer.Exit(1)

    _ok(f"{len(activities)} atividades carregadas.")

    _section("Filtros")

    _window("Semanas", "[dim]Espaço  selecionar    Enter  confirmar[/dim]")
    console.print()

    week_choices = [
        questionary.Choice(title=caption, value=num)
        for num, caption in get_unique_weeks(activities)
    ]
    while True:
        selected_week_nums = questionary.checkbox(
            "Selecione as semanas:",
            choices=week_choices,
            style=STYLE,
        ).ask()
        if selected_week_nums is None:
            _err("Cancelado.")
            raise typer.Exit(0)
        if selected_week_nums:
            break
        console.print("  [yellow]Selecione ao menos uma semana.[/yellow]")

    console.print()
    _window("Disciplinas", "[dim]Espaço  selecionar    Enter  confirmar[/dim]")
    console.print()

    subject_choices = [s for s in SUBJECTS if s != "Não presente no módulo"]
    while True:
        selected_subjects = questionary.checkbox(
            "Selecione as disciplinas:",
            choices=subject_choices,
            style=STYLE,
        ).ask()
        if selected_subjects is None:
            _err("Cancelado.")
            raise typer.Exit(0)
        if selected_subjects:
            break
        console.print("  [yellow]Selecione ao menos uma disciplina.[/yellow]")

    filtered = filter_activities(
        activities=activities,
        weeks=selected_week_nums,
        subjects=selected_subjects,
        teacher_subjects=teacher_subjects,
    )

    _section("Resultados")

    if not filtered:
        _info("Nenhuma atividade corresponde aos filtros selecionados.")
        console.print()
        raise typer.Exit(0)

    written_uuids = load_written_uuids()
    new_activities = [a for a in filtered if a.uuid not in written_uuids]
    already_count = len(filtered) - len(new_activities)

    _info(
        f"{len(filtered)} encontradas  •  "
        f"[green]{len(new_activities)} novas[/green]  •  "
        f"[dim]{already_count} já escritas[/dim]"
    )

    if not new_activities:
        _ok("Nada novo para adicionar — arquivos estão atualizados.")
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
