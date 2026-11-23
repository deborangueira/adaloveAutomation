import pytest
from adalove.models.activity import Activity
from adalove.models.section_info import SectionInfo
from cli.server import create_app


@pytest.fixture(autouse=True)
def clean_config(tmp_path, monkeypatch):
    fake_path = tmp_path / "config.json"
    monkeypatch.setattr("adalove.config.settings.CONFIG_PATH", fake_path)
    return fake_path


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("cli.server.OUTPUT_ROOT", tmp_path / "output")
    return create_app().test_client()


def make_activity(professor="Prof A", axis_caption="COM", type=2, folder_number=1, caption="Aula"):
    return Activity(
        uuid=caption + str(folder_number),
        caption=caption,
        description="",
        url="",
        professor_name=professor,
        folder_caption=f"Semana {folder_number:02d}",
        folder_number=folder_number,
        study_type="class",
        status=1,
        tags=[],
        type=type,
        axis_caption=axis_caption,
        date="2026-08-04T11:00:00Z",
    )


class _FakeClient:
    def __init__(self, api_url, token, activities=None, section=None):
        self.api_url = api_url
        self.token = token
        self._activities = activities or []
        self._section = section or SectionInfo("T1", "Módulo", "", "Fulano", "Grupo", "2026-08-03")

    def fetch_activities(self):
        return self._activities

    def fetch_section_overview(self):
        return self._section, self._activities

    def fetch_sections(self):
        return [
            {"uuid": "sec1", "caption": "2026-2A-T17", "status": "closed", "date": "2026-08-01", "projectCaption": "Módulo 7"},
            {"uuid": "sec2", "caption": "2026-2B-T17", "status": "open", "date": "2026-10-14", "projectCaption": "Módulo 8"},
        ]


def test_home_shows_setup_link_when_not_configured(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Configurar credenciais" in resp.get_data(as_text=True)


def test_home_shows_dashboard_link_when_configured(client):
    from adalove.config.settings import save_config
    save_config({"api_url": "https://example.com", "token": "Bearer x", "teacher_subjects": {}})

    resp = client.get("/")
    assert "Abrir Dashboard" in resp.get_data(as_text=True)


def test_dashboard_redirects_home_when_not_configured(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_setup_manual_get_renders_form(client):
    resp = client.get("/setup/manual")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'name="api_url"' in body
    assert 'name="token"' in body


def test_setup_manual_submit_saves_config_when_all_teachers_inferred(client, monkeypatch):
    activities = [make_activity(professor="Prof A", axis_caption="COM")]
    monkeypatch.setattr("cli.server.AdaloveClient", lambda api_url, token: _FakeClient(api_url, token, activities))

    resp = client.post("/setup/manual", data={"api_url": "https://example.com", "token": "Bearer x"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"

    from adalove.config.settings import load_config
    saved = load_config()
    assert saved["teacher_subjects"] == {"Prof A": "Programação"}


def test_setup_manual_submit_shows_subject_form_for_unmapped_teacher(client, monkeypatch):
    activities = [make_activity(professor="Prof Sem Eixo", axis_caption="")]
    monkeypatch.setattr("cli.server.AdaloveClient", lambda api_url, token: _FakeClient(api_url, token, activities))

    resp = client.post("/setup/manual", data={"api_url": "https://example.com", "token": "Bearer x"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Prof Sem Eixo" in body
    assert 'name="subject__Prof Sem Eixo"' in body
    assert 'name="api_url" value="https://example.com"' in body


def test_setup_subjects_submit_saves_chosen_mapping(client, monkeypatch):
    activities = [make_activity(professor="Prof Sem Eixo", axis_caption="")]
    monkeypatch.setattr("cli.server.AdaloveClient", lambda api_url, token: _FakeClient(api_url, token, activities))

    resp = client.post("/setup/subjects", data={
        "api_url": "https://example.com",
        "token": "Bearer x",
        "subject__Prof Sem Eixo": "Matemática",
    })
    assert resp.status_code == 302

    from adalove.config.settings import load_config
    saved = load_config()
    assert saved["teacher_subjects"] == {"Prof Sem Eixo": "Matemática"}


def test_dashboard_view_renders_generated_html(client, monkeypatch):
    from adalove.config.settings import save_config
    save_config({"api_url": "https://example.com", "token": "Bearer x", "teacher_subjects": {"Prof A": "Programação"}})

    activities = [make_activity(professor="Prof A", axis_caption="COM", type=2, folder_number=1, caption="Aula Solo")]
    monkeypatch.setattr("cli.server.AdaloveClient", lambda api_url, token: _FakeClient(api_url, token, activities))
    monkeypatch.setattr("cli.server.token_expired", lambda token: False)

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Aula Solo" in body
    assert "<script" in body


def test_switch_turma_updates_config_and_redirects(client, monkeypatch):
    from adalove.config.settings import load_config, save_config
    save_config({"api_url": "https://apiv2.inteli.edu.br/sections/sec1/userdata", "token": "Bearer x", "teacher_subjects": {}})

    activities = [make_activity(professor="Prof A", axis_caption="COM")]
    monkeypatch.setattr("cli.server.AdaloveClient", lambda api_url, token: _FakeClient(api_url, token, activities))

    resp = client.post("/turma", data={"section_uuid": "sec2"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard"

    saved = load_config()
    assert "sec2" in saved["api_url"]


def test_dashboard_with_section_query_param(client, monkeypatch):
    from adalove.config.settings import load_config, save_config
    save_config({"api_url": "https://apiv2.inteli.edu.br/sections/sec1/userdata", "token": "Bearer x", "teacher_subjects": {}})

    activities = [make_activity(professor="Prof A", axis_caption="COM")]
    monkeypatch.setattr("cli.server.AdaloveClient", lambda api_url, token: _FakeClient(api_url, token, activities))
    monkeypatch.setattr("cli.server.token_expired", lambda token: False)

    resp = client.get("/dashboard?section=sec2")
    assert resp.status_code == 200

    saved = load_config()
    assert "sec2" in saved["api_url"]



# ── browser capture: one at a time, never hangs the page ──────────────────────

def test_second_click_during_capture_gets_waiting_page(client, monkeypatch):
    import threading

    from adalove.config.settings import save_config
    save_config({"api_url": "https://apiv2.inteli.edu.br/sections/sec1/userdata", "token": "Bearer x", "teacher_subjects": {}})
    monkeypatch.setattr("cli.server.token_expired", lambda token: True)

    started, release = threading.Event(), threading.Event()
    calls = []

    def slow_capture():
        calls.append(1)
        started.set()
        release.wait(5)
        raise PermissionError("Login não detectado")

    monkeypatch.setattr("cli.server._capture_credentials", slow_capture)

    first = {}
    t = threading.Thread(target=lambda: first.setdefault("resp", client.application.test_client().get("/dashboard")))
    t.start()
    assert started.wait(5)

    resp = client.get("/dashboard")
    body = resp.get_data(as_text=True)
    assert "Aguardando login" in body
    assert "/capture/wait?next=/dashboard" in body
    assert client.get("/setup").get_data(as_text=True).count("Aguardando login") == 1
    assert "Aguardando login" in client.get("/capture/wait?next=/dashboard").get_data(as_text=True)

    release.set()
    t.join(5)
    assert len(calls) == 1  # extra clicks never started another browser
    assert "Login não detectado" in first["resp"].get_data(as_text=True)


def test_capture_wait_after_failed_capture_goes_home(client, monkeypatch):
    from adalove.config.settings import save_config
    save_config({"api_url": "https://example.com", "token": "Bearer x", "teacher_subjects": {}})
    monkeypatch.setattr("cli.server.token_expired", lambda token: True)

    resp = client.get("/capture/wait?next=/dashboard")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_capture_wait_after_successful_capture_continues(client, monkeypatch):
    from adalove.config.settings import save_config
    save_config({"api_url": "https://example.com", "token": "Bearer x", "teacher_subjects": {}})
    monkeypatch.setattr("cli.server.token_expired", lambda token: False)

    resp = client.get("/capture/wait?next=/dashboard")
    assert resp.headers["Location"] == "/dashboard"


def test_capture_wait_rejects_open_redirect(client):
    resp = client.get("/capture/wait?next=https://evil.example")
    assert resp.headers["Location"] == "/"


def test_setup_falls_back_to_manual_without_playwright(client, monkeypatch):
    def no_playwright():
        raise ImportError("Playwright não está instalado.")

    monkeypatch.setattr("cli.server._capture_credentials", no_playwright)
    resp = client.get("/setup")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/setup/manual"


def test_idle_timeout_middleware_tracks_requests(tmp_path, monkeypatch):
    from cli import server

    created = []

    class _FakeWatchdog:
        def __init__(self, idle_seconds, on_idle):
            self.started = self.finished = 0
            created.append(self)

        def request_started(self):
            self.started += 1

        def request_finished(self):
            self.finished += 1

        def start(self):
            pass

    monkeypatch.setattr(server, "IdleWatchdog", _FakeWatchdog)
    monkeypatch.setattr(server, "OUTPUT_ROOT", tmp_path / "output")
    c = server.create_app(idle_timeout=60).test_client()
    c.get("/")
    assert created[0].started == 1 and created[0].finished == 1


def test_teacher_names_from_the_api_are_escaped(client, monkeypatch):
    activities = [make_activity(professor="<script>alert(1)</script>", axis_caption="")]
    monkeypatch.setattr("cli.server.AdaloveClient", lambda api_url, token: _FakeClient(api_url, token, activities))

    body = client.post("/setup/manual", data={"api_url": "https://example.com", "token": "Bearer x"}).get_data(as_text=True)
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body


def test_cross_site_post_is_rejected(client):
    resp = client.post("/turma", data={"section_uuid": "sec2"}, headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403


def test_same_origin_post_is_allowed(client):
    resp = client.post("/turma", data={"section_uuid": ""}, headers={"Origin": "http://localhost"})
    assert resp.status_code == 302


def test_non_loopback_host_is_rejected(client):
    """A page on evil.example whose DNS points at 127.0.0.1 still sends its own Host."""
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 403
