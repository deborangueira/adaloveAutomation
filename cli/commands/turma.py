"""`adalove turma`: pick which turma is active."""

from adalove.api.client import AdaloveClient, build_section_url as _build_section_url
from adalove.config.settings import load_config, save_config
from adalove.services.turmas import activate_section
from cli.auth import _call_api, _pick_section
from cli.ui import _err, _info, _ok, _section, console


def escolher_turma() -> None:
    """Permite ao usuário escolher qual turma deseja ativar."""
    _section("Escolher Turma")

    try:
        config = load_config()
    except FileNotFoundError as e:
        _err(str(e))
        return

    console.print("  Buscando turmas disponíveis...")
    try:
        config, sections = _call_api(config, lambda c: c.fetch_sections())
    except (ConnectionError, ValueError, KeyError) as e:
        _err(str(e))
        return

    if not sections:
        _err("Nenhuma turma encontrada na API.")
        return

    selected = _pick_section(sections, config.get("api_url", ""), "Selecione a turma:")
    if not selected:
        _err("Cancelado.")
        return

    selected_uuid = selected.get("uuid")
    config["section_caption"] = selected.get("caption")

    console.print()
    console.print(f"  Carregando dados de [bold]{selected.get('caption')}[/bold]...")
    try:
        client = AdaloveClient(api_url=_build_section_url(selected_uuid), token=config["token"])
        sec, activities = client.fetch_section_overview()
        activate_section(config, selected_uuid, sec, activities)
    except (PermissionError, ConnectionError, ValueError) as e:
        activate_section(config, selected_uuid)
        _info(f"Aviso ao carregar atividades: {e}")

    save_config(config)
    _ok(f"Turma ativa alterada para [bold]{selected.get('caption')}[/bold] — {selected.get('projectCaption')}.")
    console.print()
