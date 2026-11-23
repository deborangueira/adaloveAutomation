"""Entry point (`adalove`): the Typer app, its commands and the interactive
main menu. Each command lives in cli/commands/."""

import questionary
import typer

from adalove.api.client import extract_section_uuid as _extract_section_uuid
from adalove.config.settings import load_config
from cli.commands.abrir_dashboard import gerar_tudo_turma
from cli.commands.fetch import fetch
from cli.commands.progresso import dashboard
from cli.commands.serve import serve
from cli.commands.setup import check, setup
from cli.commands.turma import escolher_turma
from cli.ui import STYLE, _header, _window, console

app = typer.Typer(
    help="Fetch and filter Adalove activities.",
    add_completion=False,
    invoke_without_command=True,
)

app.command(name="turma")(escolher_turma)
app.command()(check)
app.command()(setup)
app.command()(fetch)
app.command()(serve)


@app.callback()
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return

    while True:
        _header("Gerenciador de Atividades")

        turma_info = ""
        try:
            cfg = load_config()
            caption = cfg.get("section_caption")
            if not caption:
                uuid = _extract_section_uuid(cfg.get("api_url", ""))
                caption = uuid[:8] if uuid else None
            if caption:
                turma_info = f"[dim]Turma ativa: [bold cyan]{caption}[/bold cyan][/dim]\n"
        except Exception:
            pass

        _window(
            "Menu Principal",
            f"{turma_info}[dim]↑ ↓  navegar    Enter  confirmar[/dim]",
        )
        console.print()

        choice = questionary.select(
            "Escolha uma opção:",
            choices=[
                questionary.Choice("  Abrir Dashboard —  Calendário, Projeto, Prova e Ponderadas em um só HTML", value="tudo"),
                questionary.Choice("  Trocar Turma    —  Selecionar qual turma visualizar",                      value="turma"),
                questionary.Choice("  Progresso       —  Ver frequência e progresso",                             value="dashboard"),
                questionary.Choice("  Setup           —  Configurar credenciais e mapeamento de professores",       value="setup"),
                questionary.Choice("  Sair",                                                                       value="exit"),
            ],
            style=STYLE,
        ).ask()

        if choice is None or choice == "exit":
            raise typer.Exit(0)

        try:
            if choice == "setup":
                check(ctx)
            elif choice == "turma":
                escolher_turma()
            elif choice == "tudo":
                gerar_tudo_turma()
            elif choice == "dashboard":
                dashboard()
        except typer.Exit:
            pass


if __name__ == "__main__":
    app()
