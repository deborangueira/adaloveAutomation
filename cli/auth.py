"""Credentials in the terminal: browser capture or manual entry, teacher
mapping, and the token policy every API-calling command goes through
(`_call_api`)."""

import questionary
import typer

from adalove.api.client import AdaloveClient, build_section_url as _build_section_url
from adalove.api.client import extract_section_uuid as _extract_section_uuid, token_expired
from adalove.config.settings import load_config, save_config
from adalove.config.subjects import SUBJECTS
from adalove.filters.activity import get_unique_teachers
from adalove.services.teachers import resolve_teacher_mapping
from adalove.services.turmas import choice_title, sort_sections as _sort_sections
from cli.ui import STYLE, _err, _info, _ok, _section, console


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
    selected_caption = ""
    try:
        client = AdaloveClient(api_url=api_url, token=token)
        sections = []
        try:
            if hasattr(client, "fetch_sections"):
                sections = client.fetch_sections()
        except Exception:
            pass

        if len(sections) > 1:
            _section("Seleção de Turma")
            selected = _pick_section(sections, api_url, "Escolha a turma que deseja utilizar:")
            if selected:
                api_url = _build_section_url(selected.get("uuid"))
                selected_caption = selected.get("caption")
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

    teacher_subjects, unmapped = resolve_teacher_mapping(activities, existing_map)
    for teacher, subject in teacher_subjects.items():
        if teacher in existing_map:
            _info(f"{subject} → {teacher}")
        else:
            _ok(f"{subject} → {teacher}  [dim](inferido automaticamente pelo eixo)[/dim]")
    for teacher in unmapped:
        subject = questionary.select(
            f"{teacher}:",
            choices=SUBJECTS,
            style=STYLE,
        ).ask()
        if subject is None:
            _err("Cancelado.")
            raise typer.Exit(0)
        teacher_subjects[teacher] = subject

    cfg_data = {
        "api_url": api_url,
        "token": token,
        "teacher_subjects": teacher_subjects,
    }
    if selected_caption:
        cfg_data["section_caption"] = selected_caption
    save_config(cfg_data)

    _section("Concluído")
    _ok("Configuração salva em config.json.")
    _info("Execute [bold]adalove[/bold] e escolha Buscar para gerar seus arquivos de atividades.")
    console.print()


def _recapture_and_reload() -> dict:
    """Handle an expired/invalid token: try automatic browser recapture first (falling
    back to manual entry), persist the refreshed credentials via `_run_setup`, and return
    the freshly saved config so the caller can retry its request.

    Raises typer.Exit(1) if the user's Adalove browser session itself is invalid
    (capture_credentials raised PermissionError) — there's nothing to fall back to there.
    """
    old_uuid = None
    try:
        old_config = load_config()
        old_uuid = _extract_section_uuid(old_config.get("api_url", ""))
    except Exception:
        pass

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

    if old_uuid:
        api_url = _build_section_url(old_uuid)

    console.print()
    _run_setup(api_url, new_token)
    return load_config()


def _call_api(config: dict, op):
    """Run `op(client)` under the CLI's token policy: refresh an already
    expired token up front, and recapture once if the API still rejects it.
    Returns (config, result) — config may hold refreshed credentials.
    ConnectionError/ValueError/KeyError propagate to the caller."""
    config = _ensure_fresh_token(config)
    try:
        return config, op(AdaloveClient(api_url=config["api_url"], token=config["token"]))
    except PermissionError:
        config = _recapture_and_reload()
        return config, op(AdaloveClient(api_url=config["api_url"], token=config["token"]))


def _pick_section(sections: list[dict], current_api_url: str, prompt: str) -> dict | None:
    current_uuid = _extract_section_uuid(current_api_url)
    choices = [
        questionary.Choice(title=choice_title(s, current_uuid), value=s)
        for s in _sort_sections(sections)
    ]
    return questionary.select(prompt, choices=choices, style=STYLE).ask()


def _ensure_fresh_token(config: dict) -> dict:
    """Proactively refresh the token if it's already expired, instead of waiting
    for the API to reject it with a 401. Adalove tokens last ~1h, so after any
    real gap between uses (the common case) the saved token is guaranteed stale —
    this skips that guaranteed-to-fail first request straight to recapture.
    """
    if token_expired(config.get("token", "")):
        config = _recapture_and_reload()
    return config
