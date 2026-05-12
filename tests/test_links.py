import pytest
from adalove.models.activity import Activity
from adalove.writers.links import write_links_md


@pytest.fixture
def tmp_output(tmp_path, monkeypatch):
    monkeypatch.setattr("adalove.writers.links.OUTPUT_DIR", tmp_path)
    return tmp_path


def make_activity(caption, professor, folder_number, folder_caption, url="https://ex.com", tags=None):
    return Activity(
        uuid="x",
        caption=caption,
        description="",
        url=url,
        professor_name=professor,
        folder_caption=folder_caption,
        folder_number=folder_number,
        study_type="class",
        status=1,
        tags=tags or [],
    )


TEACHER_SUBJECTS = {"Prof A": "Programação", "Prof B": "Matemática"}


def test_write_creates_file(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05")]
    path = write_links_md(activities, TEACHER_SUBJECTS, [5], ["Programação"])
    assert path.exists()


def test_file_contains_markdown_link(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05", url="https://youtube.com")]
    path = write_links_md(activities, TEACHER_SUBJECTS, [5], ["Programação"])
    content = path.read_text(encoding="utf-8")
    assert "- [Aula 1](https://youtube.com)" in content


def test_file_skips_activities_without_url(tmp_output):
    activities = [
        make_activity("Com URL", "Prof A", 5, "Semana 05", url="https://ex.com"),
        make_activity("Sem URL", "Prof A", 5, "Semana 05", url=""),
    ]
    path = write_links_md(activities, TEACHER_SUBJECTS, [5], ["Programação"])
    content = path.read_text(encoding="utf-8")
    assert "Sem URL" not in content
    assert "Com URL" in content


def test_file_grouped_by_week_then_subject(tmp_output):
    activities = [
        make_activity("Aula Mat", "Prof B", 5, "Semana 05"),
        make_activity("Aula Prog", "Prof A", 5, "Semana 05"),
    ]
    path = write_links_md(activities, TEACHER_SUBJECTS, [5], ["Programação", "Matemática"])
    content = path.read_text(encoding="utf-8")
    assert "### Matemática" in content
    assert "### Programação" in content


def test_no_description_in_links_file(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05")]
    path = write_links_md(activities, TEACHER_SUBJECTS, [5], ["Programação"])
    content = path.read_text(encoding="utf-8")
    assert "**Professor:**" not in content
    assert "**URL:**" not in content
