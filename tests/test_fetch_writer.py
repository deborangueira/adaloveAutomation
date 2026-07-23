import pytest
from adalove.models.activity import Activity
from adalove.writers.fetch import MODE_COMPLETO, MODE_DESCRICAO, MODE_LINK, write_fetch_md


@pytest.fixture
def tmp_output(tmp_path, monkeypatch):
    monkeypatch.setattr("adalove.writers.fetch.OUTPUT_DIR", tmp_path)
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


def test_write_creates_file_at_turma_buscar_path(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05")]
    paths = write_fetch_md(activities, TEACHER_SUBJECTS, [5], ["Programação"], "2026-2A-T17")
    assert len(paths) == 1
    assert paths[0].exists()
    assert paths[0].parent == tmp_output / "2026-2A-T17" / "buscar"


def test_multiple_subjects_produce_one_file_each(tmp_output):
    activities = [
        make_activity("Aula Prog", "Prof A", 1, "Semana 01"),
        make_activity("Aula Mat", "Prof B", 1, "Semana 01"),
    ]
    paths = write_fetch_md(activities, TEACHER_SUBJECTS, [1, 2, 3], ["Programação", "Matemática"], "T1")
    names = sorted(p.name for p in paths)
    assert names == ["matemática_semana-01-02-03_completo.md", "programação_semana-01-02-03_completo.md"]


def test_multiple_weeks_stay_in_the_same_subject_file(tmp_output):
    activities = [
        make_activity("Aula A", "Prof A", 1, "Semana 01"),
        make_activity("Aula B", "Prof A", 3, "Semana 03"),
    ]
    paths = write_fetch_md(activities, TEACHER_SUBJECTS, [1, 2, 3], ["Programação"], "T1")
    assert len(paths) == 1
    content = paths[0].read_text(encoding="utf-8")
    assert "Semana 01" in content
    assert "Semana 03" in content


def test_missing_turma_falls_back_to_placeholder(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05")]
    paths = write_fetch_md(activities, TEACHER_SUBJECTS, [5], ["Programação"], "")
    assert paths[0].parent == tmp_output / "turma-desconhecida" / "buscar"


def test_file_contains_week_heading_and_activity_title(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05")]
    paths = write_fetch_md(activities, TEACHER_SUBJECTS, [5], ["Programação"], "T1")
    content = paths[0].read_text(encoding="utf-8")
    assert "## Semana 05" in content
    assert "#### Aula 1" in content


def test_file_contains_link_inline_right_under_professor(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05", url="https://youtube.com/xyz")]
    paths = write_fetch_md(activities, TEACHER_SUBJECTS, [5], ["Programação"], "T1")
    lines = paths[0].read_text(encoding="utf-8").splitlines()
    professor_line = lines.index("**Professor:** Prof A")
    assert lines[professor_line + 1] == "**Link:** https://youtube.com/xyz"


def test_file_omits_link_line_when_empty(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05", url="")]
    paths = write_fetch_md(activities, TEACHER_SUBJECTS, [5], ["Programação"], "T1")
    content = paths[0].read_text(encoding="utf-8")
    assert "**Link:**" not in content


def test_no_trailing_links_roundup_section(tmp_output):
    activities = [
        make_activity("Aula 1", "Prof A", 5, "Semana 05", url="https://ex.com/1"),
        make_activity("Sem URL", "Prof A", 5, "Semana 05", url=""),
    ]
    paths = write_fetch_md(activities, TEACHER_SUBJECTS, [5], ["Programação"], "T1")
    content = paths[0].read_text(encoding="utf-8")
    assert "## Links" not in content
    assert "**Link:** https://ex.com/1" in content


def test_weeks_sorted_ascending_in_detail_section(tmp_output):
    activities = [
        make_activity("Aula A", "Prof A", 6, "Semana 06"),
        make_activity("Aula B", "Prof A", 5, "Semana 05"),
    ]
    paths = write_fetch_md(activities, TEACHER_SUBJECTS, [5, 6], ["Programação"], "T1")
    content = paths[0].read_text(encoding="utf-8")
    assert content.index("Semana 05") < content.index("Semana 06")


def test_subject_with_no_matching_activities_produces_no_file(tmp_output):
    activities = [make_activity("Aula Prog", "Prof A", 1, "Semana 01")]
    paths = write_fetch_md(activities, TEACHER_SUBJECTS, [1], ["Programação", "Matemática"], "T1")
    assert len(paths) == 1
    assert paths[0].name.startswith("programação")


def test_mode_completo_is_the_default_and_has_title_professor_link_and_description(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05", url="https://ex.com/1", description="Descrição X")]
    paths = write_fetch_md(activities, TEACHER_SUBJECTS, [5], ["Programação"], "T1")
    assert paths[0].name.endswith("_completo.md")
    content = paths[0].read_text(encoding="utf-8")
    assert "#### Aula 1" in content
    assert "**Professor:** Prof A" in content
    assert "**Link:** https://ex.com/1" in content
    assert "Descrição X" in content


def test_mode_descricao_omits_link_but_keeps_title_professor_and_description(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05", url="https://ex.com/1", description="Descrição X")]
    paths = write_fetch_md(activities, TEACHER_SUBJECTS, [5], ["Programação"], "T1", mode=MODE_DESCRICAO)
    assert paths[0].name.endswith("_descricao.md")
    content = paths[0].read_text(encoding="utf-8")
    assert "#### Aula 1" in content
    assert "**Professor:** Prof A" in content
    assert "**Link:**" not in content
    assert "Descrição X" in content


def test_mode_link_is_a_compact_list_without_title_professor_or_description(tmp_output):
    activities = [
        make_activity("Aula 1", "Prof A", 5, "Semana 05", url="https://ex.com/1", description="Descrição X"),
        make_activity("Sem URL", "Prof A", 5, "Semana 05", url=""),
    ]
    paths = write_fetch_md(activities, TEACHER_SUBJECTS, [5], ["Programação"], "T1", mode=MODE_LINK)
    assert paths[0].name.endswith("_link.md")
    content = paths[0].read_text(encoding="utf-8")
    assert "- [Aula 1](https://ex.com/1)" in content
    assert "#### Aula 1" not in content
    assert "**Professor:**" not in content
    assert "Descrição X" not in content
    assert "Sem URL" not in content


def test_invalid_mode_raises(tmp_output):
    activities = [make_activity("Aula 1", "Prof A", 5, "Semana 05")]
    with pytest.raises(ValueError):
        write_fetch_md(activities, TEACHER_SUBJECTS, [5], ["Programação"], "T1", mode="bogus")
