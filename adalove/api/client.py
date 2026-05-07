import requests
from adalove.models.activity import Activity

SESSION_EXPIRED_MESSAGE = (
    "Session expired. Run 'adalove setup' to update your token."
)


class AdaloveClient:
    def __init__(self, api_url: str, token: str) -> None:
        self._api_url = api_url
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": token,
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://adalove.inteli.edu.br",
            "Referer": "https://adalove.inteli.edu.br/",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        })

    def fetch_activities(self) -> list[Activity]:
        try:
            response = self._session.get(self._api_url, timeout=30)
        except UnicodeEncodeError as e:
            raise ValueError(
                f"Token or URL contains non-ASCII characters ({e}). "
                "Re-run 'adalove setup' and copy the raw token from devtools."
            ) from e
        except requests.RequestException as e:
            raise ConnectionError(str(e)) from e

        if response.status_code in (401, 403):
            raise PermissionError(SESSION_EXPIRED_MESSAGE)

        response.raise_for_status()

        data = response.json()
        return [Activity.from_api(a) for a in data.get("activities", [])]
