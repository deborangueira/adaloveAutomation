"""`adalove fetch`: free filter by week/discipline into Markdown files."""

import questionary
import typer

from adalove.config.settings import load_config
from adalove.config.subjects import SUBJECTS
from adalove.filters.activity import filter_activities, get_unique_weeks
from adalove.writers.fetch import MODE_COMPLETO, MODE_DESCRICAO, MODE_LINK, write_fetch_md
from cli.auth import _call_api
from cli.files import _choose_output_dir, _reveal_in_finder
from cli.ui import STYLE, _err, _info, _ok, _section, _window, console


def fetch() -> None:
    """Filtra atividades interativamente e gera os arquivos markdown de saída."""
    _section("Carregando")

    try:
        config = load_config()
    except FileNotFoundError as e:
        _err(str(e))
        raise typer.Exit(1)

    console.print("  Buscando atividades...")
    try:
        config, (section, activities) = _call_api(config, lambda c: c.fetch_section_overview())
    except KeyError as e:
        _err(f"config.json não possui a chave {e}. Execute o setup novamente.")
        raise typer.Exit(1)
    except (ConnectionError, ValueError) as e:
        _err(str(e))
        raise typer.Exit(1)
    teacher_subjects: dict[str, str] = config.get("teacher_subjects", {})

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

    output_dir = _choose_output_dir()
    paths = write_fetch_md(
        filtered, teacher_subjects, selected_week_nums, selected_subjects, section.section_caption,
        content_mode, output_dir,
    )

    if not paths:
        _info("Nenhum arquivo gerado — nenhuma disciplina selecionada teve atividades nas semanas escolhidas.")
        console.print()
        return

    for p in paths:
        _ok(f"[bold]{p}[/bold]")
    console.print()

    _reveal_in_finder(paths[0].parent)
