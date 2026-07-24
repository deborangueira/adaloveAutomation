import pytest
from adalove.models.activity import Activity
from adalove.writers.ponderadas import write_ponderadas_md


@pytest.fixture
def tmp_output(tmp_path, monkeypatch):
    monkeypatch.setattr("adalove.writers.ponderadas.OUTPUT_DIR", tmp_path)
    return tmp_path


def make_activity(
    caption,
    professor="",
    grade_weight=4,
    folder_number=1,
    avaliacao_markdown="",
):
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
        type=11,
        grade_weight=grade_weight,
        avaliacao_markdown=avaliacao_markdown,
    )


def test_writes_a_single_file(tmp_output):
    activities = [make_activity("Ponderada 1", professor="Prof A", folder_number=3)]
    path = write_ponderadas_md(activities, "T1", tmp_output)
    assert path == tmp_output / "T1" / "ponderadas" / "ponderadas.md"
    assert list((tmp_output / "T1" / "ponderadas").iterdir()) == [path]


def test_week_section_has_one_table_row_per_ponderada_with_labeled_fields(tmp_output):
    activities = [
        make_activity(
            "Desafio de Grafos",
            professor="Prof A",
            grade_weight=5,
            folder_number=3,
            avaliacao_markdown="Critério: completude e clareza.",
        ),
    ]
    content = write_ponderadas_md(activities, "T1", tmp_output).read_text(encoding="utf-8")
    assert "## Semana 03" in content
    assert "| Ponderadas |" in content
    row = content.split("## Semana 03")[1].split("|---|")[1]
    assert "**Título:** Desafio de Grafos" in row
    assert "**Professor:** Prof A" in row
    assert "**Peso:** 5 pontos" in row
    assert "**Descrição:** Critério: completude e clareza." in row


def test_multiline_avaliacao_stays_inside_a_single_table_row(tmp_output):
    activities = [
        make_activity(
            "Ponderada 1",
            professor="Prof A",
            folder_number=3,
            avaliacao_markdown="Linha 1\nLinha 2",
        ),
    ]
    content = write_ponderadas_md(activities, "T1", tmp_output).read_text(encoding="utf-8")
    row = content.split("## Semana 03")[1].split("|---|")[1].strip().splitlines()[0]
    assert "Linha 1<br>Linha 2" in row
    assert "\nLinha 2" not in content


def test_weeks_with_no_ponderadas_are_skipped(tmp_output):
    activities = [make_activity("Ponderada 1", professor="Prof A", folder_number=3)]
    content = write_ponderadas_md(activities, "T1", tmp_output).read_text(encoding="utf-8")
    assert "## Semana 04" not in content
