"""Prototype local web server — same operations as the terminal menu (Setup,
Abrir Dashboard), but driven entirely by clicking in the browser instead of
navigating an interactive terminal prompt. Local-only (127.0.0.1), no auth of
its own: whoever can reach the terminal that started it can already read
config.json directly, so there's nothing extra to protect here.

Kept separate from cli/main.py on purpose — the terminal menu keeps working
exactly as before, this is an additive way in, not a replacement (yet).
"""

from __future__ import annotations

import re
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, url_for

from adalove.api.client import AdaloveClient, token_expired
from adalove.config.settings import load_config, save_config
from adalove.config.subjects import SUBJECTS
from adalove.filters.activity import get_unique_teachers, infer_teacher_subjects
from adalove.writers.html import write_html_dashboard

OUTPUT_ROOT = Path(__file__).resolve().parent.parent / "output"

_SHELL = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Adalove</title>
<style>
:root { color-scheme: light dark; --accent: #4f46e5; --bg: #fff; --text: #1c1f26; --muted: #6b7280; --border: #e2e4e9; }
@media (prefers-color-scheme: dark) { :root { --bg: #14161b; --text: #e7e9ee; --muted: #9aa1ad; --border: #2b2f38; --accent: #8b85ff; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
main { max-width: 560px; margin: 0 auto; padding: 3rem 1.5rem; }
h1 { font-size: 1.4rem; margin: 0 0 .5rem; }
p.sub { color: var(--muted); margin: 0 0 2rem; }
.btn {
  display: inline-flex; align-items: center; gap: .5rem; border: none; border-radius: 8px;
  background: var(--accent); color: #fff; padding: .75rem 1.25rem; font-size: .95rem;
  cursor: pointer; text-decoration: none;
}
.btn.secondary { background: transparent; color: var(--text); border: 1px solid var(--border); }
.card { border: 1px solid var(--border); border-radius: 10px; padding: 1.25rem; margin-bottom: 1rem; }
.error { color: #d64545; }
label { display: block; font-size: .85rem; color: var(--muted); margin: 1rem 0 .3rem; }
input, select { width: 100%; padding: .55rem .7rem; border-radius: 6px; border: 1px solid var(--border); background: var(--bg); color: var(--text); font-size: .9rem; }
form { margin-top: 1rem; }
</style>
</head>
<body><main>__BODY__</main></body>
</html>
"""


def _page(body: str) -> str:
    return _SHELL.replace("__BODY__", body)


def _error_page(message: str, back_href: str = "/") -> str:
    return _page(f"""
      <h1>Ops</h1>
      <p class="error">{message}</p>
      <a class="btn secondary" href="{back_href}">← Voltar</a>
    """)


def _extract_uuid(url: str) -> str | None:
    m = re.search(r"/sections/([a-f0-9]+)", url)
    return m.group(1) if m else None


def _build_section_url(section_uuid: str) -> str:
    return f"https://apiv2.inteli.edu.br/sections/{section_uuid}/userdata"


def _sort_sections(secs: list[dict]) -> list[dict]:
    return sorted(
        secs,
        key=lambda s: (0 if s.get("status") == "open" else 1, -(int((s.get("date") or "0").replace("-", "") or 0))),
    )


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def home():
        try:
            config = load_config()
            configured = True
        except FileNotFoundError:
            configured = False

        if configured:
            current_uuid = _extract_uuid(config.get("api_url", ""))
            sections = []
            try:
                client = AdaloveClient(api_url=config["api_url"], token=config["token"])
                if hasattr(client, "fetch_sections"):
                    sections = _sort_sections(client.fetch_sections())
            except Exception:
                sections = []

            current_caption = config.get("section_caption") or ""
            current_project = ""
            current_status = ""
            if sections:
                for s in sections:
                    if s.get("uuid") == current_uuid or (not current_uuid and not current_caption):
                        current_caption = s.get("caption", "")
                        current_project = s.get("projectCaption", "")
                        current_status = "Aberta" if s.get("status") == "open" else "Fechada"
                        break

            if not current_caption:
                current_caption = current_uuid or "Turma ativa"

            turma_options = ""
            if sections:
                turma_options = "".join(
                    f'<option value="{s.get("uuid")}" {"selected" if s.get("uuid") == current_uuid else ""}>'
                    f'{s.get("caption")} ({"Aberta" if s.get("status") == "open" else "Fechada"}) — {s.get("projectCaption", "")}'
                    f'</option>'
                    for s in sections
                )

            body = f"""
              <h1>Adalove</h1>
              <p class="sub">Credenciais configuradas.</p>
              <div class="card">
                <label style="margin-top:0">Turma selecionada</label>
                <div style="font-size:1.15rem;font-weight:600;margin-bottom:0.25rem;">
                  {current_caption} {f'<span style="font-size:0.75rem;font-weight:normal;padding:2px 8px;border-radius:12px;background:var(--accent);color:#fff;vertical-align:middle;margin-left:0.4rem;">{current_status}</span>' if current_status else ''}
                </div>
                {f'<p style="color:var(--muted);font-size:0.85rem;margin:0 0 1.25rem;">{current_project}</p>' if current_project else '<div style="margin-bottom:1rem;"></div>'}
                
                <a class="btn" href="/dashboard" style="margin-bottom:1.25rem;">Abrir Dashboard</a>

                {f'''
                <form method="post" action="/turma">
                  <label>Escolher outra turma</label>
                  <div style="display:flex;gap:0.5rem;align-items:center;margin-top:0.3rem;">
                    <select name="section_uuid" style="flex:1;">
                      {turma_options}
                    </select>
                    <button class="btn secondary" type="submit" style="white-space:nowrap;padding:0.55rem 1rem;">Trocar</button>
                  </div>
                </form>
                ''' if turma_options else ''}
              </div>
              <a class="btn secondary" href="/setup">Reconfigurar credenciais</a>
            """
        else:
            body = """
              <h1>Adalove</h1>
              <p class="sub">Ainda sem credenciais configuradas.</p>
              <a class="btn" href="/setup">Configurar credenciais</a>
            """
        return _page(body)

    @app.post("/turma")
    def switch_turma():
        section_uuid = request.form.get("section_uuid")
        if not section_uuid:
            return redirect(url_for("home"))
        try:
            config = load_config()
        except FileNotFoundError:
            return redirect(url_for("home"))

        new_api_url = _build_section_url(section_uuid)
        config["api_url"] = new_api_url
        client = AdaloveClient(api_url=new_api_url, token=config["token"])
        try:
            sec, acts = client.fetch_section_overview()
            config["section_caption"] = sec.section_caption
            inferred = infer_teacher_subjects(acts)
            for t in get_unique_teachers(acts):
                if t not in config.get("teacher_subjects", {}) and t in inferred:
                    config.setdefault("teacher_subjects", {})[t] = inferred[t]
        except Exception:
            pass
        save_config(config)
        return redirect(url_for("dashboard_view"))

    @app.get("/setup")
    def setup_start():
        try:
            from adalove.browser.capture import capture_credentials
        except ImportError:
            return redirect(url_for("setup_manual"))

        try:
            api_url, token = capture_credentials()
        except (PermissionError, TimeoutError, ValueError) as e:
            return _error_page(f"Captura automática falhou: {e}")
        return _finish_setup(api_url, token)

    @app.get("/setup/manual")
    def setup_manual():
        return _page("""
          <h1>Configuração manual</h1>
          <p class="sub">Cole a URL da API e o token capturados no DevTools do navegador.</p>
          <form method="post" action="/setup/manual">
            <label>URL completa da API</label>
            <input name="api_url" required>
            <label>Cabeçalho Authorization</label>
            <input name="token" type="password" required>
            <button class="btn" style="margin-top:1.25rem" type="submit">Validar e continuar</button>
          </form>
        """)

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

        teachers = get_unique_teachers(activities)
        if not teachers:
            return _error_page("Nenhum professor encontrado na resposta da API.")

        try:
            existing_map: dict[str, str] = load_config().get("teacher_subjects", {})
        except FileNotFoundError:
            existing_map = {}
        inferred = infer_teacher_subjects(activities)

        unmapped = [t for t in teachers if t not in existing_map and t not in inferred]
        if unmapped:
            rows = "".join(
                f'<label>{t}</label>'
                f'<select name="subject__{t}">'
                + "".join(f'<option value="{s}">{s}</option>' for s in SUBJECTS)
                + "</select>"
                for t in unmapped
            )
            # api_url/token ride along as hidden fields — this is a prototype
            # for local-only use (127.0.0.1), so a round-trip through the
            # user's own browser isn't a meaningful new exposure.
            return _page(f"""
              <h1>Disciplinas</h1>
              <p class="sub">Não deu pra inferir a disciplina de {len(unmapped)} professor(es) — escolha manualmente.</p>
              <form method="post" action="/setup/subjects">
                <input type="hidden" name="api_url" value="{api_url}">
                <input type="hidden" name="token" value="{token}">
                {rows}
                <button class="btn" style="margin-top:1.25rem" type="submit">Salvar</button>
              </form>
            """)

        teacher_subjects = {t: (existing_map.get(t) or inferred[t]) for t in teachers}
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

        teachers = get_unique_teachers(activities)
        try:
            existing_map: dict[str, str] = load_config().get("teacher_subjects", {})
        except FileNotFoundError:
            existing_map = {}
        inferred = infer_teacher_subjects(activities)

        teacher_subjects = {}
        for t in teachers:
            chosen = request.form.get(f"subject__{t}")
            teacher_subjects[t] = chosen or existing_map.get(t) or inferred.get(t) or SUBJECTS[-1]

        save_config({"api_url": api_url, "token": token, "teacher_subjects": teacher_subjects})
        return redirect(url_for("home"))

    @app.get("/dashboard")
    def dashboard_view():
        try:
            config = load_config()
        except FileNotFoundError:
            return redirect(url_for("home"))

        req_section = request.args.get("section")
        if req_section:
            new_api_url = _build_section_url(req_section)
            if new_api_url != config.get("api_url"):
                config["api_url"] = new_api_url
                client = AdaloveClient(api_url=new_api_url, token=config["token"])
                try:
                    sec, acts = client.fetch_section_overview()
                    config["section_caption"] = sec.section_caption
                    inferred = infer_teacher_subjects(acts)
                    for t in get_unique_teachers(acts):
                        if t not in config.get("teacher_subjects", {}) and t in inferred:
                            config.setdefault("teacher_subjects", {})[t] = inferred[t]
                except Exception:
                    pass
                save_config(config)

        if token_expired(config.get("token", "")):
            try:
                from adalove.browser.capture import capture_credentials
                api_url, token = capture_credentials()
            except (ImportError, PermissionError, TimeoutError, ValueError) as e:
                return _error_page(f"Token expirado e recaptura automática falhou: {e}", back_href="/setup/manual")
            curr_uuid = _extract_uuid(config.get("api_url", ""))
            if curr_uuid:
                config["api_url"] = _build_section_url(curr_uuid)
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

        sections = []
        try:
            if hasattr(client, "fetch_sections"):
                sections = _sort_sections(client.fetch_sections())
        except Exception:
            sections = []

        current_uuid = _extract_uuid(config.get("api_url", ""))
        available_turmas = [
            {
                "uuid": s.get("uuid"),
                "caption": s.get("caption"),
                "projectCaption": s.get("projectCaption"),
                "status": s.get("status"),
                "active": (s.get("uuid") == current_uuid) or (s.get("caption") == section.section_caption),
            }
            for s in sections
        ] if sections else None

        path = write_html_dashboard(activities, section, teacher_subjects, OUTPUT_ROOT, available_turmas=available_turmas)
        return path.read_text(encoding="utf-8")

    return app
