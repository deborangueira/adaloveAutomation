import base64
import json
import re
import time
from dataclasses import dataclass

import requests
from adalove.models.activity import Activity
from adalove.models.section_info import SectionInfo
from adalove.models.student_status import StudentStatus

API_BASE = "https://apiv2.inteli.edu.br"

SESSION_EXPIRED_MESSAGE = (
    "Sessão expirada. Execute 'adalove setup' para atualizar seu token."
)

_EXPIRY_LEEWAY_S = 30
_TIMEOUT_S = 30
_SECTION_UUID_RE = re.compile(r"/sections/([a-f0-9]+)")


def build_section_url(section_uuid: str) -> str:
    """The per-turma endpoint that returns the student's whole module."""
    return f"{API_BASE}/sections/{section_uuid}/userdata"


def extract_section_uuid(api_url: str) -> str | None:
    match = _SECTION_UUID_RE.search(api_url or "")
    return match.group(1) if match else None


def token_expired(token: str) -> bool:
    """Check the token's JWT `exp` claim locally, without any network call.

    Adalove tokens live ~1h, so after any real gap between uses the saved token
    is already stale — trying it first is a guaranteed-fail round trip. This lets
    callers skip straight to a refresh instead. Returns False (fail-open) if the
    token isn't a decodable JWT or has no `exp`; the 401 handling in the client
    below remains the safety net for that case.
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


@dataclass
class UserData:
    """Everything one `/sections/<uuid>/userdata` response carries."""

    section: SectionInfo
    activities: list[Activity]
    student_status: StudentStatus
    section_date: str


class AdaloveClient:
    """Thin HTTP client for Adalove's API.

    Errors are normalised for callers: PermissionError (401/403, the token
    is expired or invalid), ConnectionError (network), ValueError (a token or
    URL that can't be sent, e.g. pasted with non-ASCII characters).
    """

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

    # Kept for existing callers; same as the module-level function.
    build_section_url = staticmethod(build_section_url)

    def _get_json(self, url: str):
        try:
            response = self._session.get(url, timeout=_TIMEOUT_S)
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
        return response.json()

    def fetch_sections(self) -> list[dict]:
        """Every turma the student belongs to."""
        data = self._get_json(f"{API_BASE}/sections")
        return data if isinstance(data, list) else []

    def fetch_userdata(self) -> UserData:
        """One request, every view of the turma's data."""
        data = self._get_json(self._api_url)
        return UserData(
            section=SectionInfo.from_api(data),
            activities=[Activity.from_api(a) for a in data.get("activities", [])],
            student_status=StudentStatus.from_api(data.get("studentStatus") or {}),
            section_date=(data.get("section") or {}).get("sectionDate") or "",
        )

    # Narrow views over fetch_userdata(), for callers that need only part.

    def fetch_activities(self) -> list[Activity]:
        return self.fetch_userdata().activities

    def fetch_student_status(self) -> StudentStatus:
        return self.fetch_userdata().student_status

    def fetch_dashboard_data(self) -> tuple[StudentStatus, list[Activity], str]:
        data = self.fetch_userdata()
        return data.student_status, data.activities, data.section_date

    def fetch_section_overview(self) -> tuple[SectionInfo, list[Activity]]:
        data = self.fetch_userdata()
        return data.section, data.activities
