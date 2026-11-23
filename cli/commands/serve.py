"""`adalove serve`: local web server alternative to the terminal menu."""

import sys
import webbrowser

from cli.ui import _ok


def serve(port: int = 5000, idle_minutes: int = 120) -> None:
    """Sobe um servidor local e abre o navegador — protótipo pra ir reduzindo o
    uso do terminal: Setup e Abrir Dashboard viram páginas em vez de prompts.

    Substitui qualquer servidor anterior ainda rodando e se encerra sozinho
    após `idle_minutes` sem uso (0 desativa), pra nunca ficar um servidor
    antigo — com código/dependências velhos — esquecido em segundo plano."""
    import atexit
    import signal
    import threading

    from adalove.browser.capture import kill_active_captures
    from cli.server import create_app
    from cli.server_runtime import PIDFILE, remove_pidfile, stop_previous_instance, write_pidfile

    old_pid = stop_previous_instance(PIDFILE)
    if old_pid:
        _ok(f"Servidor anterior (PID {old_pid}) encerrado.")
    write_pidfile(PIDFILE)
    atexit.register(remove_pidfile, PIDFILE)
    atexit.register(kill_active_captures)
    # SIGTERM (e.g. from a newer `adalove serve`) → normal exit, so the atexit
    # hooks above still run instead of leaving a Chromium/driver behind.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    url = f"http://127.0.0.1:{port}/"
    idle_note = f", encerra após {idle_minutes} min sem uso" if idle_minutes > 0 else ""
    _ok(f"Servidor local em [bold]{url}[/bold]  [dim](Ctrl+C para parar{idle_note})[/dim]")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        create_app(idle_timeout=idle_minutes * 60 if idle_minutes > 0 else None).run(port=port, debug=False)
    except KeyboardInterrupt:
        pass
