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


def _row(content: str, label: str) -> str:
    return next(line for line in content.splitlines() if line.startswith(f"| **{label}**"))


def test_summary_header_includes_every_week_even_without_a_ponderada_or_aula(tmp_output):
    activities = [
        make_activity("Aula 1", professor="Prof A", type=2, folder_number=1, date="2026-05-04T11:00:00Z"),
        make_activity("Aula 2", professor="Prof A", type=2, folder_number=2, date="2026-05-11T11:00:00Z"),
        make_activity("Ponderada 1", professor="Prof A", type=11, grade_weight=4, folder_number=3),
    ]
    content = write_calendario_md(activities, "T1", TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    summary = content.split("## Resumo do Módulo")[1].split("## Sprint")[0]
    assert "| Semana 01 | Semana 02 | Semana 03 |" in summary


def test_ponderadas_row_is_empty_for_weeks_without_a_ponderada(tmp_output):
    activities = [
        make_activity("Aula 1", professor="Prof A", type=2, folder_number=1, date="2026-05-04T11:00:00Z"),
        make_activity("Ponderada 1", professor="Prof A", type=11, grade_weight=4, folder_number=2),
    ]
    content = write_calendario_md(activities, "T1", TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    row = _row(content, "Ponderadas")
    assert row == "| **Ponderadas** |  | _<span style=\"color:#1baf7a\">Programação</span>_ |"


def test_ponderadas_row_lists_multiple_disciplines_for_the_same_week(tmp_output):
    activities = [
        make_activity("Ponderada 1", professor="Prof A", type=11, grade_weight=4, folder_number=3),
        make_activity("Ponderada 2", professor="Prof B", type=11, grade_weight=6, folder_number=3),
    ]
    subjects = {"Prof A": "Programação", "Prof B": "Matemática"}
    content = write_calendario_md(activities, "T1", subjects, tmp_output).read_text(encoding="utf-8")
    row = _row(content, "Ponderadas")
    assert "Programação" in row and "Matemática" in row


def test_composicao_row_is_empty_for_a_week_with_no_aula_de_instrucao(tmp_output):
    activities = [make_activity("Ponderada 1", professor="Prof A", type=11, grade_weight=4, folder_number=1)]
    content = write_calendario_md(activities, "T1", TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    row = _row(content, "Composição de aulas")
    assert row == "| **Composição de aulas** |  |"


def test_composicao_row_is_solid_color_when_only_one_discipline_that_week(tmp_output):
    activities = [
        make_activity("Aula 1", professor="Prof A", type=2, folder_number=1, date="2026-05-04T11:00:00Z"),
        make_activity("Aula 2", professor="Prof A", type=2, folder_number=1, date="2026-05-06T11:00:00Z"),
    ]
    content = write_calendario_md(activities, "T1", TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    row = _row(content, "Composição de aulas")
    assert row.count("<span") == 1
    assert "#1baf7a" in row  # Programação's color
    assert ">██████████<" in row  # 10 blocks, all Programação
    assert "display:inline-block" not in row  # forced width caused mid-bar wrapping


def test_composicao_row_mixes_colors_for_multiple_disciplines(tmp_output):
    activities = [
        make_activity("Aula Prog", professor="Prof A", type=2, folder_number=2, date="2026-05-11T11:00:00Z"),
        make_activity("Aula Prog 2", professor="Prof A", type=2, folder_number=2, date="2026-05-11T11:00:00Z"),
        make_activity("Aula Prog 3", professor="Prof A", type=2, folder_number=2, date="2026-05-11T11:00:00Z"),
        make_activity("Aula Mat", professor="Prof B", type=2, folder_number=2, date="2026-05-12T11:00:00Z"),
    ]
    subjects = {"Prof A": "Programação", "Prof B": "Matemática"}
    content = write_calendario_md(activities, "T1", subjects, tmp_output).read_text(encoding="utf-8")
    row = _row(content, "Composição de aulas")
    assert row.count("<span") == 2
    assert "#1baf7a" in row and "#2a78d6" in row  # Programação and Matemática colors
    assert ">████████<" in row  # 3 Prog aulas out of 4 → 8 of 10 blocks
    assert ">██<" in row  # 1 Mat aula out of 4 → 2 of 10 blocks


def test_composicao_row_orders_segments_chronologically_not_alphabetically(tmp_output):
    """Negócios' aula happens before Programação's that week, so its color
    segment must come first in the bar — alphabetically Programação would
    win, which is exactly the wrong order here."""
    activities = [
        make_activity("Aula Negócios", professor="Prof C", type=2, folder_number=1, date="2026-05-04T11:00:00Z"),
        make_activity("Aula Programação", professor="Prof A", type=2, folder_number=1, date="2026-05-06T11:00:00Z"),
    ]
    subjects = {"Prof A": "Programação", "Prof C": "Negócios"}
    content = write_calendario_md(activities, "T1", subjects, tmp_output).read_text(encoding="utf-8")
    row = _row(content, "Composição de aulas")
    assert row.index("#eda100") < row.index("#1baf7a")  # Negócios before Programação


def test_composicao_row_ignores_encontro_de_projeto(tmp_output):
    """type 1 (Encontro de Projeto) isn't an aula de instrução, so it shouldn't
    count toward the composition bar even though it's an "encontro"."""
    activities = [make_activity("Orientação", professor="Prof A", type=1, folder_number=1, date="2026-05-04T11:00:00Z")]
    content = write_calendario_md(activities, "T1", TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    row = _row(content, "Composição de aulas")
    assert row == "| **Composição de aulas** |  |"


def test_artefatos_row_counts_artifacts_only_on_even_weeks(tmp_output):
    activities = [
        make_activity("Artefato Sprint 1", type=21, folder_number=2),
        make_activity("Ponderada 1", professor="Prof A", type=11, grade_weight=4, folder_number=1),
    ]
    content = write_calendario_md(activities, "T1", TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    row = _row(content, "Artefatos")
    assert row == "| **Artefatos** |  | 1 |"


def test_artefatos_row_counts_multiple_artifacts_the_same_week(tmp_output):
    activities = [
        make_activity("Artefato 1", type=21, folder_number=2),
        make_activity("Artefato 2", type=21, folder_number=2),
    ]
    content = write_calendario_md(activities, "T1", TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    row = _row(content, "Artefatos")
    assert row == "| **Artefatos** | 2 |"
