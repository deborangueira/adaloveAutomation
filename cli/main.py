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

from adalove.api.client import AdaloveClient, token_expired
from adalove.config.settings import load_config, save_config
from adalove.models.dashboard_metrics import DashboardMetrics
from adalove.config.subjects import SUBJECTS
from adalove.filters.activity import (
    filter_activities,
    get_ponderadas,
    get_project_artifacts,
    get_unique_teachers,
    get_unique_weeks,
    infer_teacher_subjects,
)
from adalove.writers.fetch import MODE_COMPLETO, MODE_DESCRICAO, MODE_LINK, write_fetch_md
from adalove.writers.ponderadas import write_ponderadas_md
from adalove.writers.project import write_project_md
from adalove.writers.subject_links import write_subject_links_md

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

    config = _ensure_fresh_token(config)

    console.print("  Conectando...")
    try:
        client = AdaloveClient(api_url=config["api_url"], token=config["token"])
        student_status, activities, section_date = client.fetch_dashboard_data()
    except KeyError as e:
        _err(f"config.json não possui a chave {e}. Execute o Setup novamente.")
        return
    except PermissionError:
        try:
            config = _recapture_and_reload()
            client = AdaloveClient(api_url=config["api_url"], token=config["token"])
            student_status, activities, section_date = client.fetch_dashboard_data()
        except (ConnectionError, ValueError) as e:
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


def turma_info() -> None:
    """Mostra a turma/módulo da sessão atual e o mapeamento de professores, para
    conferir que o token configurado se refere à turma certa antes de usar o resto
    das ferramentas."""
    _section("Turma Atual")

    try:
        config = load_config()
    except FileNotFoundError as e:
        _err(str(e))
        return

    config = _ensure_fresh_token(config)
    teacher_subjects: dict[str, str] = config.get("teacher_subjects", {})

    console.print("  Buscando informações da turma...")
    try:
        client = AdaloveClient(api_url=config["api_url"], token=config["token"])
        section, activities = client.fetch_section_overview()
    except KeyError as e:
        _err(f"config.json não possui a chave {e}. Execute o setup novamente.")
        return
    except PermissionError:
        try:
            config = _recapture_and_reload()
            teacher_subjects = config.get("teacher_subjects", {})
            client = AdaloveClient(api_url=config["api_url"], token=config["token"])
            section, activities = client.fetch_section_overview()
        except (ConnectionError, ValueError) as e:
            _err(str(e))
            return
    except (ConnectionError, ValueError) as e:
        _err(str(e))
        return

    console.print()
    info_tbl = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0, 2))
    info_tbl.add_column("label", style="dim")
    info_tbl.add_column("value", style="bold white")
    info_tbl.add_row("Turma", section.section_caption)
    info_tbl.add_row("Módulo", section.project_caption)
    info_tbl.add_row("Descrição", section.project_description)
    info_tbl.add_row("Orientador(a)", section.advisor_name)
    info_tbl.add_row("Grupo", section.group_caption)
    info_tbl.add_row("Data da seção", section.section_date)
    console.print(info_tbl)

    _section("Disciplinas → Professores")

    teachers = get_unique_teachers(activities)
    inferred = infer_teacher_subjects(activities)
    if not teachers:
        _info("Nenhum professor encontrado nas atividades.")
    else:
        for teacher in teachers:
            subject = teacher_subjects.get(teacher)
            if subject:
                console.print(f"  [dim]•[/dim]  [bold]{subject}[/bold] → {teacher}")
            elif teacher in inferred:
                console.print(
                    f"  [dim]•[/dim]  [bold]{inferred[teacher]}[/bold] → {teacher} "
                    "[dim](inferido pelo eixo, não salvo — rode o Setup)[/dim]"
                )
            else:
                console.print(f"  [bold yellow]•[/bold yellow]  [yellow]sem disciplina mapeada[/yellow] → {teacher}")

    console.print()
    result = questionary.select(
        "Turma",
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

    while True:
        _header("Gerenciador de Atividades")

        _window(
            "Menu Principal",
            "[dim]↑ ↓  navegar    Enter  confirmar[/dim]",
        )
        console.print()

        choice = questionary.select(
            "Escolha uma opção:",
            choices=[
                questionary.Choice("  Turma      —  Ver turma e professores da sessão atual",            value="turma"),
                questionary.Choice("  Ponderadas —  Todas as ponderadas da turma",            value="ponderadas"),
                questionary.Choice("  Projeto    —  Todos os artefatos do projeto",                    value="project"),
                questionary.Choice("  Prova      —  Todos os Autoestudos da prova", value="subject"),
                questionary.Choice("  Buscar     —  Baixar autoestudos por semana e disciplina",                        value="fetch"),
                questionary.Choice("  Dashboard  —  Ver frequência e progresso",                        value="dashboard"),
                questionary.Choice("  Setup      —  Configurar credenciais e mapeamento de professores", value="setup"),
                questionary.Choice("  Sair",                                                              value="exit"),
            ],
            style=STYLE,
        ).ask()

        if choice is None or choice == "exit":
            raise typer.Exit(0)

        try:
            if choice == "setup":
                check(ctx)
            elif choice == "fetch":
                ctx.invoke(fetch)
            elif choice == "subject":
                subject_export()
            elif choice == "project":
                project_export()
            elif choice == "dashboard":
                dashboard()
            elif choice == "ponderadas":
                ponderadas_export()
            elif choice == "turma":
                turma_info()
        except typer.Exit:
            pass


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

    config = _ensure_fresh_token(config)

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
        _recapture_and_reload()
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

    try:
        existing_map: dict[str, str] = load_config().get("teacher_subjects", {})
    except FileNotFoundError:
        existing_map = {}

    inferred = infer_teacher_subjects(activities)

    teacher_subjects: dict[str, str] = {}
    for teacher in teachers:
        if teacher in existing_map:
            subject = existing_map[teacher]
            teacher_subjects[teacher] = subject
            _info(f"{subject} → {teacher}")
        elif teacher in inferred:
            subject = inferred[teacher]
            teacher_subjects[teacher] = subject
            _ok(f"{subject} → {teacher}  [dim](inferido automaticamente pelo eixo)[/dim]")
        else:
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

    _info("Configurando sessão pelo navegador...")
    _info("Uma aba pode abrir e fechar sozinha em alguns segundos — é esperado.")
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


def _recapture_and_reload() -> dict:
    """Handle an expired/invalid token: try automatic browser recapture first (falling
    back to manual entry), persist the refreshed credentials via `_run_setup`, and return
    the freshly saved config so the caller can retry its request.

    Raises typer.Exit(1) if the user's Adalove browser session itself is invalid
    (capture_credentials raised PermissionError) — there's nothing to fall back to there.
    """
    _err("Token expirado ou inválido.")
    console.print()
    _info("Configurando sessão automaticamente pelo navegador...")
    _info("Uma aba pode abrir e fechar sozinha em alguns segundos — é esperado.")
    console.print()
    try:
        from adalove.browser.capture import capture_credentials
        api_url, new_token = capture_credentials()
        _ok("Credenciais capturadas automaticamente.")
    except ImportError:
        _info("Playwright não instalado — voltando para configuração manual.")
        console.print()
        api_url, new_token = _prompt_credentials()
    except PermissionError as e:
        _err(str(e))
        raise typer.Exit(1)
    except (TimeoutError, ValueError) as e:
        _err(f"Captura automática falhou: {e}")
        _info("Voltando para configuração manual.")
        console.print()
        api_url, new_token = _prompt_credentials()

    console.print()
    _run_setup(api_url, new_token)
    return load_config()


def _ensure_fresh_token(config: dict) -> dict:
    """Proactively refresh the token if it's already expired, instead of waiting
    for the API to reject it with a 401. Adalove tokens last ~1h, so after any
    real gap between uses (the common case) the saved token is guaranteed stale —
    this skips that guaranteed-to-fail first request straight to recapture.
    """
    if token_expired(config.get("token", "")):
        config = _recapture_and_reload()
    return config


# ── subject export ────────────────────────────────────────────────────────────

_MODO_PROVA_WEEKS = range(1, 9)


def subject_export() -> None:
    """Gera um arquivo .md por disciplina com todos os links das 8 primeiras semanas."""
    _section("Carregando")

    try:
        config = load_config()
    except FileNotFoundError as e:
        _err(str(e))
        return

    config = _ensure_fresh_token(config)
    teacher_subjects: dict[str, str] = config.get("teacher_subjects", {})

    console.print("  Buscando atividades...")
    try:
        client = AdaloveClient(api_url=config["api_url"], token=config["token"])
        section, activities = client.fetch_section_overview()
    except KeyError as e:
        _err(f"config.json não possui a chave {e}. Execute o setup novamente.")
        return
    except PermissionError:
        try:
            config = _recapture_and_reload()
            teacher_subjects = config.get("teacher_subjects", {})
            client = AdaloveClient(api_url=config["api_url"], token=config["token"])
            section, activities = client.fetch_section_overview()
        except (ConnectionError, ValueError) as e:
            _err(str(e))
            return
    except (ConnectionError, ValueError) as e:
        _err(str(e))
        return

    _ok(f"{len(activities)} atividades carregadas.")

    filtered = [a for a in activities if a.folder_number in _MODO_PROVA_WEEKS]

    _section("Resultados")

    paths = write_subject_links_md(filtered, teacher_subjects, section.section_caption)

    if not paths:
        _info("Nenhuma atividade com disciplina mapeada encontrada.")
        return

    for p in paths:
        _ok(f"[bold]{p}[/bold]")
    console.print()


# ── project export ────────────────────────────────────────────────────────────

def project_export() -> None:
    """Gera um único .md com os artefatos de projeto (Desenvolvimento de Projeto),
    organizados por sprint."""
    _section("Carregando")

    try:
        config = load_config()
    except FileNotFoundError as e:
        _err(str(e))
        return

    config = _ensure_fresh_token(config)

    console.print("  Buscando atividades...")
    try:
        client = AdaloveClient(api_url=config["api_url"], token=config["token"])
        section, activities = client.fetch_section_overview()
    except KeyError as e:
        _err(f"config.json não possui a chave {e}. Execute o setup novamente.")
        return
    except PermissionError:
        try:
            config = _recapture_and_reload()
            client = AdaloveClient(api_url=config["api_url"], token=config["token"])
            section, activities = client.fetch_section_overview()
        except (ConnectionError, ValueError) as e:
            _err(str(e))
            return
    except (ConnectionError, ValueError) as e:
        _err(str(e))
        return

    _ok(f"{len(activities)} atividades carregadas.")

    _section("Resultados")

    artifacts = get_project_artifacts(activities)
    if not artifacts:
        _info("Nenhum artefato de projeto encontrado nesta turma.")
        return

    paths = write_project_md(activities, section.section_caption)
    _ok(f"{len(artifacts)} artefatos encontrados.")
    for p in paths:
        _ok(f"[bold]{p}[/bold]")
    console.print()


# ── ponderadas export ─────────────────────────────────────────────────────────

def ponderadas_export() -> None:
    """Gera um .md por semana com atividades ponderadas, mais um consolidado."""
    _section("Carregando")

    try:
        config = load_config()
    except FileNotFoundError as e:
        _err(str(e))
        return

    config = _ensure_fresh_token(config)

    console.print("  Buscando atividades...")
    try:
        client = AdaloveClient(api_url=config["api_url"], token=config["token"])
        section, activities = client.fetch_section_overview()
    except KeyError as e:
        _err(f"config.json não possui a chave {e}. Execute o setup novamente.")
        return
    except PermissionError:
        try:
            config = _recapture_and_reload()
            client = AdaloveClient(api_url=config["api_url"], token=config["token"])
            section, activities = client.fetch_section_overview()
        except (ConnectionError, ValueError) as e:
            _err(str(e))
            return
    except (ConnectionError, ValueError) as e:
        _err(str(e))
        return

    _ok(f"{len(activities)} atividades carregadas.")

    _section("Resultados")

    ponderadas = get_ponderadas(activities)
    if not ponderadas:
        _info("Nenhuma atividade ponderada encontrada nesta turma.")
        return

    paths = write_ponderadas_md(activities, section.section_caption)
    _ok(f"{len(ponderadas)} atividades ponderadas encontradas.")
    for p in paths:
        _ok(f"[bold]{p}[/bold]")
    console.print()


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

    config = _ensure_fresh_token(config)
    teacher_subjects: dict[str, str] = config.get("teacher_subjects", {})

    console.print("  Buscando atividades...")
    try:
        client = AdaloveClient(api_url=config["api_url"], token=config["token"])
        section, activities = client.fetch_section_overview()
    except KeyError as e:
        _err(f"config.json não possui a chave {e}. Execute o setup novamente.")
        raise typer.Exit(1)
    except PermissionError:
        try:
            config = _recapture_and_reload()
            teacher_subjects = config.get("teacher_subjects", {})
            client = AdaloveClient(api_url=config["api_url"], token=config["token"])
            section, activities = client.fetch_section_overview()
        except (ConnectionError, ValueError) as e:
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

    console.print()
    _window("Conteúdo", "[dim]Enter  confirmar[/dim]")
    console.print()

    content_mode = questionary.select(
        "O que incluir no arquivo?",
        choices=[
            questionary.Choice("Só link", value=MODE_LINK),
            questionary.Choice("Só descrição", value=MODE_DESCRICAO),
            questionary.Choice("Ambos juntos", value=MODE_COMPLETO),
        ],
        style=STYLE,
    ).ask()
    if content_mode is None:
        _err("Cancelado.")
        raise typer.Exit(0)

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

    _info(f"{len(filtered)} atividades encontradas.")

    paths = write_fetch_md(
        filtered, teacher_subjects, selected_week_nums, selected_subjects, section.section_caption, content_mode
    )

    if not paths:
        _info("Nenhum arquivo gerado — nenhuma disciplina selecionada teve atividades nas semanas escolhidas.")
        console.print()
        return

    for p in paths:
        _ok(f"[bold]{p}[/bold]")
    console.print()


if __name__ == "__main__":
    app()
