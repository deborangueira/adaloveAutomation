import pytest
from unittest.mock import MagicMock, patch
from adalove.api.client import AdaloveClient, SESSION_EXPIRED_MESSAGE
from adalove.models.activity import Activity


SAMPLE_RESPONSE = {
    "activities": [
        {
            "studentActivityUuid": "abc123",
            "caption": "Videoaula: Huffman",
            "description": "<p>Conteúdo</p>",
            "basicActivityURL": "https://youtube.com/watch?v=xyz",
            "professorName": "Fillipe Manoel Xavier Resina",
            "folderCaption": "Semana 05",
            "study_type": "class",
            "status": 1,
        }
    ]
}


@pytest.fixture
def client():
    return AdaloveClient(
        api_url="https://api.example.com/section",
        token="Bearer eyJtest",
    )


def test_fetch_activities_returns_activity_list(client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_RESPONSE

    with patch.object(client._session, "get", return_value=mock_response):
        activities = client.fetch_activities()

    assert len(activities) == 1
    assert isinstance(activities[0], Activity)
    assert activities[0].caption == "Videoaula: Huffman"
    assert activities[0].folder_number == 5


def test_fetch_activities_raises_on_401(client):
    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch.object(client._session, "get", return_value=mock_response):
        with pytest.raises(PermissionError, match=SESSION_EXPIRED_MESSAGE):
            client.fetch_activities()


def test_fetch_activities_raises_on_403(client):
    mock_response = MagicMock()
    mock_response.status_code = 403

    with patch.object(client._session, "get", return_value=mock_response):
        with pytest.raises(PermissionError, match=SESSION_EXPIRED_MESSAGE):
            client.fetch_activities()


def test_fetch_activities_raises_on_network_error(client):
    import requests
    with patch.object(client._session, "get", side_effect=requests.RequestException("timeout")):
        with pytest.raises(ConnectionError, match="timeout"):
            client.fetch_activities()


def test_client_sets_authorization_header(client):
    assert client._session.headers["Authorization"] == "Bearer eyJtest"


import requests as _requests
from adalove.models.student_status import StudentStatus

SAMPLE_RESPONSE_WITH_STATUS = {
    "activities": [],
    "studentStatus": {
        "absencesCount": 270,
        "absencesPercentage": "0.08",
        "doneEvaluationResult": "3.50",
        "evaluationResult": "4.20",
    },
}


def test_fetch_student_status_returns_student_status(client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_RESPONSE_WITH_STATUS

    with patch.object(client._session, "get", return_value=mock_response):
        status = client.fetch_student_status()

    assert isinstance(status, StudentStatus)
    assert status.absences_percentage == pytest.approx(0.08)
    assert status.absences_count == 270


def test_fetch_student_status_raises_on_401(client):
    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch.object(client._session, "get", return_value=mock_response):
        with pytest.raises(PermissionError, match=SESSION_EXPIRED_MESSAGE):
            client.fetch_student_status()


def test_fetch_student_status_raises_on_network_error(client):
    with patch.object(
        client._session, "get", side_effect=_requests.RequestException("timeout")
    ):
        with pytest.raises(ConnectionError, match="timeout"):
            client.fetch_student_status()


def test_fetch_student_status_handles_missing_key(client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}

    with patch.object(client._session, "get", return_value=mock_response):
        status = client.fetch_student_status()

    assert status.absences_percentage == 0.0


SAMPLE_FULL_RESPONSE = {
    "activities": [
        {
            "studentActivityUuid": "def456",
            "caption": "Desafio",
            "description": "",
            "basicActivityURL": "",
            "professorName": "Prof X",
            "folderCaption": "Semana 03",
            "study_type": "class",
            "status": 1,
            "type": 11,
            "gradeWeight": 3,
            "gradeResult": "-1.0",
        }
    ],
    "studentStatus": {
        "absencesCount": 270,
        "absencesPercentage": "0.08",
        "doneEvaluationResult": "3.50",
        "evaluationResult": "4.20",
    },
    "section": {
        "sectionDate": "2026-04-22",
    },
}


def test_fetch_dashboard_data_returns_tuple(client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_FULL_RESPONSE

    with patch.object(client._session, "get", return_value=mock_response):
        student_status, activities, section_date = client.fetch_dashboard_data()

    assert isinstance(student_status, StudentStatus)
    assert student_status.absences_percentage == pytest.approx(0.08)
    assert len(activities) == 1
    assert activities[0].type == 11
    assert activities[0].grade_weight == 3
    assert section_date == "2026-04-22"


def test_fetch_dashboard_data_raises_on_401(client):
    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch.object(client._session, "get", return_value=mock_response):
        with pytest.raises(PermissionError, match=SESSION_EXPIRED_MESSAGE):
            client.fetch_dashboard_data()


def test_fetch_dashboard_data_raises_on_network_error(client):
    with patch.object(
        client._session, "get", side_effect=_requests.RequestException("timeout")
    ):
        with pytest.raises(ConnectionError, match="timeout"):
            client.fetch_dashboard_data()


def test_fetch_dashboard_data_missing_section_returns_empty_date(client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"activities": [], "studentStatus": {}}

    with patch.object(client._session, "get", return_value=mock_response):
        _, _, section_date = client.fetch_dashboard_data()

    assert section_date == ""
