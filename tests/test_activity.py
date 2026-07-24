import pytest

from adalove.models.activity import Activity, strip_html


def test_strip_html_removes_tags():
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_decodes_entities():
    assert "é" in strip_html("caf&eacute;")


def test_strip_html_empty_string():
    assert strip_html("") == ""


def test_strip_html_none_like():
    assert strip_html(None) == ""


def test_activity_from_api_maps_fields():
    raw = {
        "studentActivityUuid": "abc123",
        "caption": "Videoaula: Huffman",
        "description": "<p>Conteúdo</p>",
        "basicActivityURL": "https://youtube.com/watch?v=xyz",
        "professorName": "Fillipe Manoel Xavier Resina",
        "folderCaption": "Semana 05",
        "study_type": "class",
        "status": 1,
        "tags": ["ponderada"],
    }
    activity = Activity.from_api(raw)
    assert activity.uuid == "abc123"
    assert activity.caption == "Videoaula: Huffman"
    assert activity.description == "Conteúdo"
    assert activity.url == "https://youtube.com/watch?v=xyz"
    assert activity.professor_name == "Fillipe Manoel Xavier Resina"
    assert activity.folder_caption == "Semana 05"
    assert activity.folder_number == 5
    assert activity.study_type == "class"
    assert activity.status == 1
    assert activity.tags == ["ponderada"]


def test_activity_from_api_handles_missing_url():
    raw = {
        "studentActivityUuid": "abc",
        "caption": "Leitura",
        "description": "",
        "basicActivityURL": None,
        "professorName": "Prof X",
        "folderCaption": "Semana 10",
        "study_type": "class",
        "status": 1,
    }
    activity = Activity.from_api(raw)
    assert activity.url == ""
    assert activity.folder_number == 10


def test_activity_from_api_handles_missing_professor():
    raw = {
        "studentActivityUuid": "abc",
        "caption": "Atividade",
        "description": "",
        "basicActivityURL": "",
        "professorName": None,
        "folderCaption": "Semana 02",
        "study_type": "class",
        "status": 2,
    }
    activity = Activity.from_api(raw)
    assert activity.professor_name == ""


def test_activity_from_api_handles_missing_tags():
    raw = {
        "studentActivityUuid": "abc",
        "caption": "Atividade",
        "description": "",
        "basicActivityURL": "",
        "professorName": "Prof X",
        "folderCaption": "Semana 02",
        "study_type": "class",
        "status": 1,
    }
    activity = Activity.from_api(raw)
    assert activity.tags == []


def test_activity_from_api_maps_grade_fields():
    raw = {
        "studentActivityUuid": "abc",
        "caption": "Desafio",
        "description": "",
        "basicActivityURL": "",
        "professorName": "Prof X",
        "folderCaption": "Semana 03",
        "study_type": "class",
        "status": 1,
        "type": 11,
        "gradeWeight": 4,
        "gradeResult": "8.5",
    }
    activity = Activity.from_api(raw)
    assert activity.type == 11
    assert activity.grade_weight == 4
    assert activity.grade_result == pytest.approx(8.5)


def test_activity_from_api_grade_result_missing_defaults_to_minus_one():
    raw = {
        "studentActivityUuid": "abc",
        "caption": "Leitura",
        "description": "",
        "basicActivityURL": "",
        "professorName": "Prof X",
        "folderCaption": "Semana 01",
        "study_type": "class",
        "status": 1,
    }
    activity = Activity.from_api(raw)
    assert activity.type == 0
    assert activity.grade_weight == 0
    assert activity.grade_result == pytest.approx(-1.0)
