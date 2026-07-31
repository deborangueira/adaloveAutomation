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
