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


class _MarkdownStripper(HTMLParser):
    """Unlike _HTMLStripper, keeps paragraph/line breaks and turns <strong>/<b>
    into markdown bold, since project artifact cards rely on that structure
    (headers, bullet-style lines) to stay readable — not every card follows
    the same section layout, so flattening to one line would lose it."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("strong", "b"):
            self._parts.append("**")
        elif tag == "br":
            self._parts.append("\n")
        elif tag == "li":
            self._parts.append("\n- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("strong", "b"):
            self._parts.append("**")
        elif tag == "p":
            self._parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        lines = [" ".join(line.split()) for line in raw.split("\n")]
        text = "\n".join(lines)
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        return text.strip()


def html_to_markdown(html: str | None) -> str:
    if not html:
        return ""
    stripper = _MarkdownStripper()
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
    type: int = 0
    grade_weight: int = 0
    grade_result: float = -1.0
    axis_caption: str = ""
    description_markdown: str = ""
    avaliacao_markdown: str = ""
    date: str = ""

    @property
    def is_ponderada(self) -> bool:
        return any(t.lower() == "ponderada" for t in self.tags)

    @classmethod
    def from_api(cls, data: dict) -> "Activity":
        folder_caption = data.get("folderCaption") or ""
        gr = data.get("gradeResult")
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
            type=data.get("type") or 0,
            grade_weight=data.get("gradeWeight") or 0,
            grade_result=float(gr) if gr is not None else -1.0,
            axis_caption=data.get("axisCaption") or "",
            description_markdown=html_to_markdown(data.get("description")),
            avaliacao_markdown=html_to_markdown(data.get("studyQuestion")),
            date=data.get("date") or "",
        )
