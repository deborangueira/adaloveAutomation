import pytest
from pathlib import Path
from adalove.models.activity import Activity
from adalove.output.markdown import write_activities_md


@pytest.fixture
def tmp_output(tmp_path, monkeypatch):
    monkeypatch.setattr("adalove.output.markdown.OUTPUT_DIR", tmp_path)
    return tmp_path


def make_activity(caption, professor, folder_number, folder_caption, url="https://ex.com", description="Desc", tags=None):
    return Activity(
        uuid="x",
        caption=caption,
        description=description,
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
    path = write_activities_md(activities, TEACHER_SUBJECTS, [5], ["Programação"])
    assert path.exists()


def test_file_contains_week_heading(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05")]
    path = write_activities_md(activities, TEACHER_SUBJECTS, [5], ["Programação"])
    content = path.read_text(encoding="utf-8")
    assert "## Semana 05" in content


def test_file_contains_subject_heading(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05")]
    path = write_activities_md(activities, TEACHER_SUBJECTS, [5], ["Programação"])
    content = path.read_text(encoding="utf-8")
    assert "### Programação" in content


def test_file_contains_activity_title(tmp_output):
    activities = [make_activity("Aula de Huffman", "Prof A", 5, "Semana 05")]
    path = write_activities_md(activities, TEACHER_SUBJECTS, [5], ["Programação"])
    content = path.read_text(encoding="utf-8")
    assert "#### Aula de Huffman" in content


def test_file_contains_url(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05", url="https://youtube.com/xyz")]
    path = write_activities_md(activities, TEACHER_SUBJECTS, [5], ["Programação"])
    content = path.read_text(encoding="utf-8")
    assert "https://youtube.com/xyz" in content


def test_file_omits_url_line_when_empty(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05", url="")]
    path = write_activities_md(activities, TEACHER_SUBJECTS, [5], ["Programação"])
    content = path.read_text(encoding="utf-8")
    assert "**URL:**" not in content


def test_weeks_sorted_ascending(tmp_output):
    activities = [
        make_activity("Aula A", "Prof A", 6, "Semana 06"),
        make_activity("Aula B", "Prof A", 5, "Semana 05"),
    ]
    path = write_activities_md(activities, TEACHER_SUBJECTS, [5, 6], ["Programação"])
    content = path.read_text(encoding="utf-8")
    assert content.index("Semana 05") < content.index("Semana 06")
