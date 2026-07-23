import base64
import json
import time

import requests
from adalove.models.activity import Activity
from adalove.models.section_info import SectionInfo
from adalove.models.student_status import StudentStatus

SESSION_EXPIRED_MESSAGE = (
    "Sessão expirada. Execute 'adalove setup' para atualizar seu token."
)

_EXPIRY_LEEWAY_S = 30


def token_expired(token: str) -> bool:
    """Check the token's JWT `exp` claim locally, without any network call.

    Adalove tokens live ~1h, so after any real gap between uses the saved token
    is already stale — trying it first is a guaranteed-fail round trip. This lets
    callers skip straight to a refresh instead. Returns False (fail-open) if the
    token isn't a decodable JWT or has no `exp`; the 401 handling in the fetch_*
    methods below remains the safety net for that case.
    """
    try:
        payload = token.removeprefix("Bearer ").strip().split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp")
        if exp is None:
            return False
        return time.time() >= exp - _EXPIRY_LEEWAY_S
    except Exception:
        return False


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
                f"Token ou URL contém caracteres não-ASCII ({e}). "
                "Execute 'adalove setup' novamente e copie o token bruto do devtools."
            ) from e
        except requests.RequestException as e:
            raise ConnectionError(str(e)) from e

        if response.status_code in (401, 403):
            raise PermissionError(SESSION_EXPIRED_MESSAGE)

        response.raise_for_status()

        data = response.json()
        return [Activity.from_api(a) for a in data.get("activities", [])]

    def fetch_student_status(self) -> StudentStatus:
        try:
            response = self._session.get(self._api_url, timeout=30)
        except UnicodeEncodeError as e:
            raise ValueError(
                f"Token ou URL contém caracteres não-ASCII ({e}). "
                "Execute 'adalove setup' novamente e copie o token bruto do devtools."
            ) from e
        except requests.RequestException as e:
            raise ConnectionError(str(e)) from e

        if response.status_code in (401, 403):
            raise PermissionError(SESSION_EXPIRED_MESSAGE)

        response.raise_for_status()

        data = response.json()
        return StudentStatus.from_api(data.get("studentStatus") or {})

    def fetch_dashboard_data(self) -> tuple[StudentStatus, list[Activity], str]:
        try:
            response = self._session.get(self._api_url, timeout=30)
        except UnicodeEncodeError as e:
            raise ValueError(
                f"Token ou URL contém caracteres não-ASCII ({e}). "
                "Execute 'adalove setup' novamente e copie o token bruto do devtools."
            ) from e
        except requests.RequestException as e:
            raise ConnectionError(str(e)) from e

        if response.status_code in (401, 403):
            raise PermissionError(SESSION_EXPIRED_MESSAGE)

        response.raise_for_status()

        data = response.json()
        student_status = StudentStatus.from_api(data.get("studentStatus") or {})
        activities = [Activity.from_api(a) for a in data.get("activities", [])]
        section_date = (data.get("section") or {}).get("sectionDate") or ""
        return student_status, activities, section_date

    def fetch_section_overview(self) -> tuple[SectionInfo, list[Activity]]:
        try:
            response = self._session.get(self._api_url, timeout=30)
        except UnicodeEncodeError as e:
            raise ValueError(
                f"Token ou URL contém caracteres não-ASCII ({e}). "
                "Execute 'adalove setup' novamente e copie o token bruto do devtools."
            ) from e
        except requests.RequestException as e:
            raise ConnectionError(str(e)) from e

        if response.status_code in (401, 403):
            raise PermissionError(SESSION_EXPIRED_MESSAGE)

        response.raise_for_status()

        data = response.json()
        section_info = SectionInfo.from_api(data)
        activities = [Activity.from_api(a) for a in data.get("activities", [])]
        return section_info, activities
