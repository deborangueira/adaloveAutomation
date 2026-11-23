"""Dashboard writer: renders the module report (adalove/report) as one
self-contained dashboard.html.

The report's structured data is embedded as JSON and drawn client-side by
html_assets/script.js; each tab's Markdown export is pre-rendered here by
report/markdown.py and embedded too, so the browser only triggers the
download — no formatting rules live in JavaScript.
"""

import base64
import json
import re
from html import escape
from pathlib import Path

from adalove.config.paths import OUTPUT_DIR
from adalove.config.subjects import SUBJECT_COLORS
from adalove.models.activity import Activity
from adalove.models.section_info import SectionInfo
from adalove.report.common import UNKNOWN_TURMA
from adalove.report.markdown import render_exports
from adalove.report.model import build_report

_ASSETS_DIR = Path(__file__).parent / "html_assets"
# Plus Jakarta Sans (SIL OFL 1.1, see html_assets/fonts/OFL.txt), latin
# subset, one variable file covering every weight.
_FONT_FILE = _ASSETS_DIR / "fonts" / "plus-jakarta-sans-latin-wght.woff2"

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _md_to_html(text: str) -> str:
    """Minimal renderer for the light markdown produced by
    Activity.description_markdown/avaliacao_markdown (bold via **, "- "
    bullets, blank-line paragraphs) — just enough to display that text safely,
    not a general markdown parser. Escapes first, so bold/list markers are the
    only markup that survives into the output HTML."""
    if not text:
        return ""

    def inline(line: str) -> str:
        return _BOLD_RE.sub(r"<strong>\1</strong>", escape(line))

    blocks = []
    for para in text.split("\n\n"):
        lines = [line for line in para.split("\n") if line.strip()]
        if not lines:
            continue
        if all(line.startswith("- ") for line in lines):
            items = "".join(f"<li>{inline(line[2:])}</li>" for line in lines)
            blocks.append(f"<ul>{items}</ul>")
        else:
            blocks.append(f"<p>{'<br>'.join(inline(line) for line in lines)}</p>")
    return "".join(blocks)


def _build_data(
    activities: list[Activity],
    section: SectionInfo,
    teacher_subjects: dict[str, str],
    available_turmas: list[dict] | None = None,
) -> dict:
    """The report plus what only the dashboard needs: rendered HTML for rich
    text, subject colors, the turma switcher and the Markdown exports."""
    report = build_report(activities, section, teacher_subjects)
    exports = render_exports(report)

    for sprint in report["projeto"]:
        for artifact in sprint["artifacts"]:
            artifact["html"] = _md_to_html(artifact["descriptionMarkdown"])
    for week in report["ponderadas"]:
        for item in week["items"]:
            item["html"] = _md_to_html(item["avaliacaoMarkdown"])

    return {
        **report,
        "availableTurmas": available_turmas or [],
        "subjectColors": SUBJECT_COLORS,
        "exports": exports,
    }


def write_html_dashboard(
    activities: list[Activity],
    section: SectionInfo,
    teacher_subjects: dict[str, str],
    output_dir: Path | None = None,
    available_turmas: list[dict] | None = None,
) -> Path:
    """Write a single <output_dir>/<turma>/dashboard.html (output_dir defaults
    to OUTPUT_DIR), overwritten on every run — an interactive, self-contained
    (no external assets, works straight off the filesystem) view of the
    module, with a per-tab "Exportar dados" button that downloads that tab's
    Markdown.
    """
    data = _build_data(activities, section, teacher_subjects, available_turmas=available_turmas)
    # The JSON sits inside a <script type="application/json"> tag as inert
    # text, parsed via JSON.parse() in JS — never interpreted as markup or
    # code, so a caption containing "</script>" can't break out of the tag or
    # execute. `\/` is a legal JSON escape for `/`, so this is safe wherever
    # it lands in the payload.
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    turma_dir = (output_dir or OUTPUT_DIR) / (section.section_caption or UNKNOWN_TURMA)
    turma_dir.mkdir(parents=True, exist_ok=True)

    path = turma_dir / "dashboard.html"
    path.write_text(_render_template(data_json), encoding="utf-8")
    return path


def _render_template(data_json: str) -> str:
    """Inline style.css and script.js into template.html — the shipped
    dashboard.html stays a single self-contained file (no external assets,
    works straight off the filesystem); only the source is split up."""
    template = (_ASSETS_DIR / "template.html").read_text(encoding="utf-8")
    style = (_ASSETS_DIR / "style.css").read_text(encoding="utf-8").rstrip("\n")
    script = (_ASSETS_DIR / "script.js").read_text(encoding="utf-8").rstrip("\n")
    # The font is embedded as a data: URI for the same reason — the page is
    # opened from the filesystem, often offline, so it can't fetch it.
    font_b64 = base64.b64encode(_FONT_FILE.read_bytes()).decode("ascii")
    style = style.replace("__FONT_URL__", f"data:font/woff2;base64,{font_b64}")
    return (
        template
        .replace("__STYLE__", style)
        .replace("__SCRIPT__", script)
        .replace("__DATA__", data_json)
    )
