"""Prototype local web server — same operations as the terminal menu (Setup,
Abrir Dashboard), but driven entirely by clicking in the browser instead of
navigating an interactive terminal prompt. Local-only (127.0.0.1), no auth of
its own: whoever can reach the terminal that started it can already read
config.json directly, so there's nothing extra to protect here.

Kept separate from cli/main.py on purpose — the terminal menu keeps working
exactly as before, this is an additive way in, not a replacement (yet).
"""

from __future__ import annotations

import threading
from urllib.parse import urlsplit

from flask import Flask, abort, redirect, render_template, request, url_for

from adalove.api.client import AdaloveClient, build_section_url, extract_section_uuid, token_expired
from adalove.config.paths import OUTPUT_DIR
from adalove.config.settings import load_config, save_config
from adalove.config.subjects import SUBJECTS
from adalove.services.teachers import resolve_teacher_mapping
from adalove.services.turmas import activate_section, available_turmas, sort_sections, status_label
from adalove.writers.html import write_html_dashboard
from cli.server_runtime import IdleWatchdog, interrupt_main_process

OUTPUT_ROOT = OUTPUT_DIR

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]"}

def _error_page(message: str, back_href: str = "/") -> str:
    return render_template("error.html", message=str(message), back_href=back_href)


def _switch_section(config: dict, section_uuid: str) -> dict:
    """Point config at another turma and save it. Loading that turma's data
    (name, new teachers) is best-effort: the switch still happens without it."""
    client = AdaloveClient(api_url=build_section_url(section_uuid), token=config["token"])
    try:
        section, activities = client.fetch_section_overview()
        activate_section(config, section_uuid, section, activities)
    except (PermissionError, ConnectionError, ValueError):
        activate_section(config, section_uuid)
    save_config(config)
    return config


class CaptureInProgress(Exception):
    """Another request is already waiting on the browser login."""


def _capture_credentials() -> tuple[str, str]:
    # Isolated in a child process with a hard timeout: a hung Playwright can't
    # pin a request thread (or leave a stray driver behind) forever.
    from adalove.browser.capture import capture_credentials_isolated

    return capture_credentials_isolated()


def _waiting_page(next_href: str) -> str:
    return render_template("waiting.html", next_href=next_href)


def create_app(idle_timeout: float | None = None) -> Flask:
    """idle_timeout: seconds without requests before the server shuts itself
    down (None disables it — tests and embedding)."""
    app = Flask(__name__)
    capture_lock = threading.Lock()

    @app.before_request
    def _only_from_this_machine():
        """Two cheap guards for a server with no login of its own:
        - Host must be loopback, so a hostile page can't reach us through
          DNS rebinding (its domain resolving to 127.0.0.1).
        - A POST carrying an Origin must come from this same server, so a
          hostile page can't submit forms here (CSRF). Browsers always send
          Origin on cross-site POSTs; non-browser clients may omit it."""
        host = (request.host or "").rsplit(":", 1)[0]
        if host not in _LOOPBACK_HOSTS:
            abort(403)
        origin = request.headers.get("Origin")
        if request.method == "POST" and origin and urlsplit(origin).netloc != request.host:
            abort(403)

    def run_capture() -> tuple[str, str]:
        """Only one browser capture at a time — extra clicks get a waiting
        page instead of piling up Chromium windows."""
        if not capture_lock.acquire(blocking=False):
            raise CaptureInProgress
        try:
            return _capture_credentials()
        finally:
            capture_lock.release()

    if idle_timeout:
        watchdog = IdleWatchdog(idle_timeout, on_idle=interrupt_main_process)
        app.before_request(lambda: watchdog.request_started())

        @app.teardown_request
        def _finished(_exc):
            watchdog.request_finished()

        watchdog.start()

    @app.get("/capture/wait")
    def capture_wait():
        next_href = request.args.get("next", "/")
        if next_href not in ("/", "/dashboard"):
            next_href = "/"
        if capture_lock.locked():
            return _waiting_page(next_href)
        # Capture finished: go on only if it actually left us a valid token,
        # otherwise back home — never silently start another browser window.
        try:
            config = load_config()
        except FileNotFoundError:
            return redirect(url_for("home"))
        if next_href == "/dashboard" and not token_expired(config.get("token", "")):
            return redirect(url_for("dashboard_view"))
        return redirect(url_for("home"))

    @app.get("/")
    def home():
        try:
            config = load_config()
            configured = True
        except FileNotFoundError:
            configured = False

        if configured:
            current_uuid = extract_section_uuid(config.get("api_url", ""))
            sections = []
            try:
                client = AdaloveClient(api_url=config["api_url"], token=config["token"])
                if hasattr(client, "fetch_sections"):
                    sections = sort_sections(client.fetch_sections())
            except (KeyError, PermissionError, ConnectionError, ValueError):
                sections = []  # the page still works; it just can't offer a switch

            current_caption = config.get("section_caption") or ""
            current_project = ""
            current_status = ""
            for s in sections:
                if s.get("uuid") == current_uuid or (not current_uuid and not current_caption):
                    current_caption = s.get("caption", "")
                    current_project = s.get("projectCaption", "")
                    current_status = status_label(s)
                    break

            if not current_caption:
                current_caption = current_uuid or "Turma ativa"
            return render_template(
                "home.html",
                configured=True,
                current_caption=current_caption,
                current_project=current_project,
                current_status=current_status,
                current_uuid=current_uuid,
                sections=sections,
                status_label=status_label,
            )
        return render_template("home.html", configured=False)

    @app.post("/turma")
    def switch_turma():
        section_uuid = request.form.get("section_uuid")
        if not section_uuid:
            return redirect(url_for("home"))
        try:
            config = load_config()
        except FileNotFoundError:
            return redirect(url_for("home"))
        _switch_section(config, section_uuid)
        return redirect(url_for("dashboard_view"))

    @app.get("/setup")
    def setup_start():
        try:
            api_url, token = run_capture()
        except CaptureInProgress:
            return _waiting_page("/")
        except ImportError:
            return redirect(url_for("setup_manual"))
        except (PermissionError, TimeoutError, ValueError) as e:
            return _error_page(f"Captura automática falhou: {e}")
        return _finish_setup(api_url, token)

    @app.get("/setup/manual")
    def setup_manual():
        return render_template("setup_manual.html")

    @app.post("/setup/manual")
    def setup_manual_submit():
        return _finish_setup(request.form["api_url"], request.form["token"])

    def _finish_setup(api_url: str, token: str) -> str:
        """Validate credentials and either save the mapping straight away (every
        teacher already resolved) or hand off to a form for the ones left over —
        the web equivalent of _run_setup()'s per-teacher questionary prompt."""
        try:
            client = AdaloveClient(api_url=api_url, token=token)
            activities = client.fetch_activities()
        except (PermissionError, ConnectionError, ValueError) as e:
            return _error_page(str(e), back_href="/setup/manual")

        try:
            existing_map: dict[str, str] = load_config().get("teacher_subjects", {})
        except FileNotFoundError:
            existing_map = {}
        teacher_subjects, unmapped = resolve_teacher_mapping(activities, existing_map)
        if not teacher_subjects and not unmapped:
            return _error_page("Nenhum professor encontrado na resposta da API.")

        if unmapped:
            return render_template(
                "setup_subjects.html", unmapped=unmapped, subjects=SUBJECTS, api_url=api_url, token=token
            )

        save_config({"api_url": api_url, "token": token, "teacher_subjects": teacher_subjects})
        return redirect(url_for("home"))

    @app.post("/setup/subjects")
    def setup_subjects_submit():
        api_url = request.form["api_url"]
        token = request.form["token"]
        try:
            client = AdaloveClient(api_url=api_url, token=token)
            activities = client.fetch_activities()
        except (PermissionError, ConnectionError, ValueError) as e:
            return _error_page(str(e), back_href="/setup/manual")

        try:
            existing_map: dict[str, str] = load_config().get("teacher_subjects", {})
        except FileNotFoundError:
            existing_map = {}
        teacher_subjects, unmapped = resolve_teacher_mapping(activities, existing_map)
        for t in unmapped:
            chosen = request.form.get(f"subject__{t}")
            teacher_subjects[t] = chosen if chosen in SUBJECTS else SUBJECTS[-1]

        save_config({"api_url": api_url, "token": token, "teacher_subjects": teacher_subjects})
        return redirect(url_for("home"))

    @app.get("/dashboard")
    def dashboard_view():
        try:
            config = load_config()
        except FileNotFoundError:
            return redirect(url_for("home"))

        req_section = request.args.get("section")
        if req_section and build_section_url(req_section) != config.get("api_url"):
            _switch_section(config, req_section)

        if token_expired(config.get("token", "")):
            try:
                api_url, token = run_capture()
            except CaptureInProgress:
                return _waiting_page("/dashboard")
            except (ImportError, PermissionError, TimeoutError, ValueError) as e:
                return _error_page(f"Token expirado e recaptura automática falhou: {e}", back_href="/setup/manual")
            curr_uuid = extract_section_uuid(config.get("api_url", ""))
            if curr_uuid:
                config["api_url"] = build_section_url(curr_uuid)
            else:
                config["api_url"] = api_url
            config["token"] = token
            save_config(config)

        teacher_subjects: dict[str, str] = config.get("teacher_subjects", {})
        client = AdaloveClient(api_url=config["api_url"], token=config["token"])
        try:
            section, activities = client.fetch_section_overview()
            config["section_caption"] = section.section_caption
            save_config(config)
        except PermissionError:
            return _error_page("Sessão expirada — reconfigure as credenciais.", back_href="/setup")
        except (ConnectionError, ValueError) as e:
            return _error_page(str(e))

        turmas = None
        try:
            if hasattr(client, "fetch_sections"):
                turmas = available_turmas(client.fetch_sections(), config, section.section_caption) or None
        except (PermissionError, ConnectionError, ValueError):
            turmas = None  # the switcher is optional; the dashboard still renders

        path = write_html_dashboard(activities, section, teacher_subjects, OUTPUT_ROOT, available_turmas=turmas)
        return path.read_text(encoding="utf-8")

    return app
