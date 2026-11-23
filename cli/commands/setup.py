"""`adalove setup` and `adalove check`."""

import questionary
import typer

from adalove.api.client import AdaloveClient
from adalove.config.settings import load_config
from cli.auth import _ensure_fresh_token, _prompt_credentials, _recapture_and_reload, _run_setup
from cli.ui import STYLE, _err, _info, _ok, _section, console


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
