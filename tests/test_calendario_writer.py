import pytest
from adalove.models.activity import Activity
from adalove.writers.calendario import write_calendario_md


@pytest.fixture
def tmp_output(tmp_path, monkeypatch):
    monkeypatch.setattr("adalove.writers.calendario.OUTPUT_DIR", tmp_path)
    return tmp_path


def make_activity(caption, professor="", type=0, grade_weight=0, folder_number=1, date=""):
    return Activity(
        uuid="x",
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
        grade_weight=grade_weight,
        date=date,
    )


TEACHER_SUBJECTS = {"Prof A": "Programação"}


def test_ponderada_line_includes_subject_weight_and_week(tmp_output):
    activities = [
        make_activity("Ponderada 1", professor="Prof A", type=11, grade_weight=4, folder_number=3),
    ]
    path = write_calendario_md(activities, "T1", TEACHER_SUBJECTS, tmp_output)
    content = path.read_text(encoding="utf-8")
    assert "4 pontos — Semana 03" in content


def test_ponderadas_from_different_weeks_in_same_sprint_show_their_own_week(tmp_output):
    activities = [
        make_activity("Ponderada Semana 3", professor="Prof A", type=11, grade_weight=4, folder_number=3),
        make_activity("Ponderada Semana 4", professor="Prof A", type=11, grade_weight=6, folder_number=4),
    ]
    path = write_calendario_md(activities, "T1", TEACHER_SUBJECTS, tmp_output)
    content = path.read_text(encoding="utf-8")
    assert "4 pontos — Semana 03" in content
    assert "6 pontos — Semana 04" in content
