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
