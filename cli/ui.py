"""Terminal look & feel shared by every command: console, prompt style,
banner and the one-line status helpers."""

from questionary import Style
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

console = Console()
err_console = Console(stderr=True)


BANNER = """\
 █████╗ ██████╗  █████╗ ██╗      ██████╗ ██╗   ██╗███████╗
██╔══██╗██╔══██╗██╔══██╗██║     ██╔═══██╗██║   ██║██╔════╝
███████║██║  ██║███████║██║     ██║   ██║██║   ██║█████╗
██╔══██║██║  ██║██╔══██║██║     ██║   ██║╚██╗ ██╔╝██╔══╝
██║  ██║██████╔╝██║  ██║███████╗╚██████╔╝ ╚████╔╝ ███████╗
╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝   ╚═══╝  ╚══════╝"""


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
