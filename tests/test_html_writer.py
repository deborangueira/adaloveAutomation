import json

import pytest
from adalove.models.activity import Activity
from adalove.models.section_info import SectionInfo
from adalove.writers.html import write_html_dashboard


@pytest.fixture
def tmp_output(tmp_path, monkeypatch):
    monkeypatch.setattr("adalove.writers.html.OUTPUT_DIR", tmp_path)
    return tmp_path


def make_activity(
    caption,
    professor="",
    type=0,
    grade_weight=0,
    folder_number=1,
    date="",
    url="",
    description_markdown="",
    avaliacao_markdown="",
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
        date=date,
        description_markdown=description_markdown,
        avaliacao_markdown=avaliacao_markdown,
    )


TEACHER_SUBJECTS = {"Prof A": "Programação"}


def make_section(caption="T1", modulo="", descricao="", orientador="", grupo="", data=""):
    return SectionInfo(
        section_caption=caption,
        project_caption=modulo,
        project_description=descricao,
        advisor_name=orientador,
        group_caption=grupo,
        section_date=data,
    )


def _embedded_data(html: str) -> dict:
    marker = '<script id="data" type="application/json">'
    start = html.index(marker) + len(marker)
    end = html.index("</script>", start)
    return json.loads(html[start:end])


def test_writes_a_single_file(tmp_output):
    activities = [make_activity("Aula 1", professor="Prof A", type=2, folder_number=1, date="2026-05-04T11:00:00Z")]
    path = write_html_dashboard(activities, make_section("T1"), TEACHER_SUBJECTS, tmp_output)
    assert path == tmp_output / "T1" / "dashboard.html"
    assert path.exists()


def test_embedded_data_has_turma_and_subject_colors(tmp_output):
    activities = [make_activity("Aula 1", professor="Prof A", type=2, folder_number=1, date="2026-05-04T11:00:00Z")]
    html = write_html_dashboard(activities, make_section("T1"), TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    data = _embedded_data(html)
    assert data["turma"] == "T1"
    assert data["subjectColors"]["Programação"] == "#1baf7a"


def test_ponderadas_grouped_by_week_carry_subject_and_weight(tmp_output):
    activities = [
        make_activity("Ponderada 1", professor="Prof A", type=11, grade_weight=4, folder_number=3),
    ]
    html = write_html_dashboard(activities, make_section("T1"), TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    data = _embedded_data(html)
    assert data["ponderadas"] == [
        {
            "week": 3,
            "items": [
                {
                    "caption": "Ponderada 1",
                    "professor": "Prof A",
                    "subject": "Programação",
                    "weight": 4,
                    "html": "",
                    "avaliacaoMarkdown": "",
                }
            ],
        }
    ]


def test_sprint_groups_two_weeks_and_carries_encontro_subject(tmp_output):
    activities = [
        make_activity("Aula 1", professor="Prof A", type=2, folder_number=1, date="2026-05-04T11:00:00Z"),
        make_activity("Ponderada 1", professor="Prof A", type=11, grade_weight=4, folder_number=2),
    ]
    html = write_html_dashboard(activities, make_section("T1"), TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    data = _embedded_data(html)
    assert len(data["sprints"]) == 1
    sprint = data["sprints"][0]
    assert sprint["number"] == 1
    assert sprint["encontros"][0]["subject"] == "Programação"
    assert sprint["encontros"][0]["date"] == "04/05/2026"
    assert sprint["ponderadas"][0]["weight"] == 4


def test_project_artifact_description_markdown_becomes_html(tmp_output):
    activities = [
        make_activity(
            "Artefato",
            type=21,
            folder_number=2,
            description_markdown="**Objetivo:** entregar\n\n- item 1\n- item 2",
        ),
    ]
    html = write_html_dashboard(activities, make_section("T1"), TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    data = _embedded_data(html)
    artifact_html = data["projeto"][0]["artifacts"][0]["html"]
    assert "<strong>Objetivo:</strong>" in artifact_html
    assert "<li>item 1</li>" in artifact_html
    assert "<li>item 2</li>" in artifact_html


def test_html_escapes_markdown_input(tmp_output):
    activities = [
        make_activity("Ponderada 1", professor="Prof A", type=11, grade_weight=4, folder_number=3,
                       avaliacao_markdown="<script>alert(1)</script>"),
    ]
    html = write_html_dashboard(activities, make_section("T1"), TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    data = _embedded_data(html)
    item_html = data["ponderadas"][0]["items"][0]["html"]
    assert "<script>" not in item_html
    assert "&lt;script&gt;" in item_html


def test_prova_groups_links_and_excludes_inteli_and_book_domains(tmp_output):
    activities = [
        make_activity("Aula", professor="Prof A", type=2, folder_number=1, url="https://example.com/material"),
        make_activity("Livro", professor="Prof A", type=11, url="https://minhabiblioteca.com.br/livro"),
        make_activity("Interno", professor="Prof A", type=2, url="https://inteli.edu.br/pagina"),
    ]
    html = write_html_dashboard(activities, make_section("T1"), TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    data = _embedded_data(html)
    subject = next(s for s in data["prova"] if s["name"] == "Programação")
    assert subject["links"] == ["https://example.com/material"]
    assert subject["books"] == ["https://minhabiblioteca.com.br/livro"]


def test_prova_only_covers_the_first_eight_weeks(tmp_output):
    """Same scope as cli/main.py's _MODO_PROVA_WEEKS / subject_export() —
    Material > Prova has always been about the first 8 weeks, and the
    dashboard's Prova tab (now the only place this material gets generated
    from "Exportar tudo") must keep that scope."""
    activities = [
        make_activity("Semana 8", professor="Prof A", type=2, folder_number=8, url="https://example.com/w8"),
        make_activity("Semana 9", professor="Prof A", type=2, folder_number=9, url="https://example.com/w9"),
    ]
    html = write_html_dashboard(activities, make_section("T1"), TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    data = _embedded_data(html)
    subject = next(s for s in data["prova"] if s["name"] == "Programação")
    assert subject["links"] == ["https://example.com/w8"]


def test_projeto_and_ponderadas_carry_raw_markdown_for_export(tmp_output):
    """The "Exportar dados" button rebuilds .md client-side from this raw
    text — only the pre-rendered "html" field isn't enough to reconstruct it."""
    activities = [
        make_activity("Artefato", type=21, folder_number=2, description_markdown="**Objetivo:** entregar"),
        make_activity(
            "Ponderada 1", professor="Prof A", type=11, grade_weight=4, folder_number=3,
            avaliacao_markdown="Critério: completude.",
        ),
    ]
    html = write_html_dashboard(activities, make_section("T1"), TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    data = _embedded_data(html)
    assert data["projeto"][0]["artifacts"][0]["descriptionMarkdown"] == "**Objetivo:** entregar"
    assert data["ponderadas"][0]["items"][0]["avaliacaoMarkdown"] == "Critério: completude."


def test_turma_info_carries_section_details_and_all_activities_disciplinas(tmp_output):
    """Unlike Prova (scoped to the first 8 weeks), the Turma tab's
    disciplina → professor mapping must cover the whole module — a professor
    only teaching after week 8 still needs to show up here."""
    activities = [
        make_activity("Semana 1", professor="Prof A", type=2, folder_number=1),
        make_activity("Semana 9", professor="Prof B", type=2, folder_number=9),
    ]
    teacher_subjects = {"Prof A": "Programação", "Prof B": "Matemática"}
    section = make_section(
        "T1", modulo="Módulo 6", descricao="IA aplicada", orientador="Fulano", grupo="Grupo 1", data="2026-08-03"
    )
    html = write_html_dashboard(activities, section, teacher_subjects, tmp_output).read_text(encoding="utf-8")
    data = _embedded_data(html)
    info = data["turmaInfo"]
    assert info["caption"] == "T1"
    assert info["moduloCaption"] == "Módulo 6"
    assert info["moduloDescricao"] == "IA aplicada"
    assert info["orientador"] == "Fulano"
    assert info["grupo"] == "Grupo 1"
    assert info["dataSessao"] == "2026-08-03"
    assert info["disciplinas"] == [
        {"subject": "Matemática", "professors": ["Prof B"]},
        {"subject": "Programação", "professors": ["Prof A"]},
    ]


def test_toolbar_search_and_subject_chips_are_gone(tmp_output):
    activities = [make_activity("Aula 1", professor="Prof A", type=2, folder_number=1, date="2026-05-04T11:00:00Z")]
    html = write_html_dashboard(activities, make_section("T1"), TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    assert 'id="search"' not in html
    assert 'id="subject-chips"' not in html
    assert 'class="toolbar"' not in html


def test_export_buttons_present_for_each_section(tmp_output):
    activities = [make_activity("Aula 1", professor="Prof A", type=2, folder_number=1, date="2026-05-04T11:00:00Z")]
    html = write_html_dashboard(activities, make_section("T1"), TEACHER_SUBJECTS, tmp_output).read_text(encoding="utf-8")
    for section in ("calendario", "projeto", "prova", "ponderadas"):
        assert f'id="export-{section}"' in html
