from dataclasses import dataclass
from html.parser import HTMLParser


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(" ".join(self._parts).split())


def strip_html(html: str | None) -> str:
    if not html:
        return ""
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


def _parse_folder_number(folder_caption: str) -> int:
    for part in reversed(folder_caption.strip().split()):
        try:
            return int(part)
        except ValueError:
            continue
    return 0


@dataclass
class Activity:
    uuid: str
    caption: str
    description: str
    url: str
    professor_name: str
    folder_caption: str
    folder_number: int
    study_type: str
    status: int
    tags: list[str]

    @property
    def is_ponderada(self) -> bool:
        return any(t.lower() == "ponderada" for t in self.tags)

    @classmethod
    def from_api(cls, data: dict) -> "Activity":
        folder_caption = data.get("folderCaption") or ""
        return cls(
            uuid=data.get("studentActivityUuid") or "",
            caption=data.get("caption") or "",
            description=strip_html(data.get("description")),
            url=data.get("basicActivityURL") or "",
            professor_name=data.get("professorName") or "",
            folder_caption=folder_caption,
            folder_number=_parse_folder_number(folder_caption),
            study_type=data.get("study_type") or "",
            status=data.get("status") or 0,
            tags=data.get("tags") or [],
        )
