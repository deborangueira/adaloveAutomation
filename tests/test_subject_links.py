import pytest
from adalove.models.activity import Activity
from adalove.writers.subject_links import write_subject_links_md


@pytest.fixture
def tmp_output(tmp_path, monkeypatch):
    monkeypatch.setattr("adalove.writers.subject_links.OUTPUT_DIR", tmp_path)
    return tmp_path


def make_activity(
    caption,
    professor,
    url="",
    type=0,
    grade_weight=0,
    folder_number=1,
):
    return Activity(
        uuid="x",
        caption=caption,
        description="",
        url=url,
        professor_name=professor,
        folder_caption=f"Semana {folder_number:02d}",
        folder_number=folder_number,
        study_type="class",
        status=1,
        tags=[],
        type=type,
        grade_weight=grade_weight,
    )


TEACHER_SUBJECTS = {"Prof A": "Programação"}


def test_instrucoes_section_lists_only_type_2_titles(tmp_output):
    activities = [
        make_activity("Aula 1", "Prof A", type=2),
        make_activity("Aula 2", "Prof A", type=2),
        make_activity("Autoestudo 1", "Prof A", type=11, grade_weight=0),
    ]
    paths = write_subject_links_md(activities, TEACHER_SUBJECTS, "T1")
    content = paths[0].read_text(encoding="utf-8")
    instrucoes_block = content.split("## Instruções")[1].split("## Autoestudo")[0]
    assert "- Aula 1" in instrucoes_block
    assert "- Aula 2" in instrucoes_block
    assert "Autoestudo 1" not in instrucoes_block


def test_instrucoes_grouped_by_sprint(tmp_output):
    activities = [
        make_activity("Aula Semana 1", "Prof A", type=2, folder_number=1),
        make_activity("Aula Semana 2", "Prof A", type=2, folder_number=2),
        make_activity("Aula Semana 3", "Prof A", type=2, folder_number=3),
    ]
    paths = write_subject_links_md(activities, TEACHER_SUBJECTS, "T1")
    content = paths[0].read_text(encoding="utf-8")
    instrucoes_block = content.split("## Instruções")[1].split("## Links")[0]
    sprint1_block = instrucoes_block.split("### Sprint 1")[1].split("### Sprint 2")[0]
    sprint2_block = instrucoes_block.split("### Sprint 2")[1]
    assert "- Aula Semana 1" in sprint1_block
    assert "- Aula Semana 2" in sprint1_block
    assert "- Aula Semana 3" not in sprint1_block
    assert "- Aula Semana 3" in sprint2_block
    assert content.index("### Sprint 1") < content.index("### Sprint 2")


def test_autoestudo_section_excludes_ponderadas(tmp_output):
    activities = [
        make_activity("Autoestudo 1", "Prof A", type=11, grade_weight=0),
        make_activity("Ponderada 1", "Prof A", type=11, grade_weight=4),
    ]
    paths = write_subject_links_md(activities, TEACHER_SUBJECTS, "T1")
    content = paths[0].read_text(encoding="utf-8")
    autoestudo_block = content.split("## Autoestudo")[1].split("## Links")[0]
    assert "- Autoestudo 1" in autoestudo_block
    assert "Ponderada 1" not in autoestudo_block


def test_sections_omitted_when_empty(tmp_output):
    activities = [make_activity("Encontro Projeto", "Prof A", type=1)]
    paths = write_subject_links_md(activities, TEACHER_SUBJECTS, "T1")
    content = paths[0].read_text(encoding="utf-8")
    assert "## Instruções" not in content
    assert "## Autoestudo" not in content


def test_links_section_still_includes_every_activity_with_url(tmp_output):
    activities = [
        make_activity("Aula 1", "Prof A", url="https://ex.com/1", type=2),
        make_activity("Autoestudo 1", "Prof A", url="https://ex.com/2", type=11, grade_weight=0),
    ]
    paths = write_subject_links_md(activities, TEACHER_SUBJECTS, "T1")
    content = paths[0].read_text(encoding="utf-8")
    links_block = content.split("## Links")[1]
    assert "https://ex.com/1" in links_block
    assert "https://ex.com/2" in links_block
