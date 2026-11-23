"""Menu "Abrir Dashboard": build dashboard.html and open it."""

import webbrowser

from adalove.api.client import AdaloveClient
from adalove.config.settings import load_config
from adalove.services.turmas import available_turmas
from adalove.writers.html import write_html_dashboard
from cli.auth import _call_api
from cli.files import _choose_output_dir
from cli.ui import _err, _info, _ok, _section, console


def gerar_tudo_turma() -> None:
    """Gera o dashboard interativo (Calendário, Projeto, Prova, Ponderadas e
    Turma juntos num só HTML) a partir de uma única busca de atividades, e
    abre no navegador — os arquivos .md de cada material são gerados sob
    demanda pelo próprio dashboard, no botão "Exportar dados" de cada aba."""
    _section("Carregando")

    try:
        config = load_config()
    except FileNotFoundError as e:
        _err(str(e))
        return

    console.print("  Buscando atividades...")
    try:
        config, (section, activities) = _call_api(config, lambda c: c.fetch_section_overview())
    except KeyError as e:
        _err(f"config.json não possui a chave {e}. Execute o setup novamente.")
        return
    except (ConnectionError, ValueError) as e:
        _err(str(e))
        return
    teacher_subjects: dict[str, str] = config.get("teacher_subjects", {})

    _ok(f"{len(activities)} atividades carregadas.")

    _section("Resultados")

    output_dir = _choose_output_dir()

    # The turma switcher is a nice-to-have: without it the dashboard still works.
    turmas = None
    try:
        client = AdaloveClient(api_url=config["api_url"], token=config["token"])
        turmas = available_turmas(client.fetch_sections(), config, section.section_caption)
    except (PermissionError, ConnectionError, ValueError) as e:
        _info(f"Lista de turmas indisponível: {e}")

    dashboard_path = write_html_dashboard(
        activities, section, teacher_subjects, output_dir, available_turmas=turmas
    )
    _ok(f"Dashboard  —  [bold]{dashboard_path}[/bold]")

    console.print()

    webbrowser.open(dashboard_path.resolve().as_uri())
