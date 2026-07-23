from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from adalove.filters.activity import get_project_artifacts, sprint_number
from adalove.models.activity import Activity

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


def _resolve_run_dir() -> Path:
    """Reuse today's existing output subfolder (matched by date only, ignoring
    the time) instead of creating a new timestamped one on every run."""
    today = date.today().isoformat()
    if OUTPUT_DIR.is_dir():
        for entry in sorted(OUTPUT_DIR.iterdir()):
            if entry.is_dir() and entry.name.startswith(today):
                return entry
    stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    run_dir = OUTPUT_DIR / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_project_md(activities: list[Activity]) -> Path:
    artifacts = get_project_artifacts(activities)

    grouped: dict[int, list[Activity]] = defaultdict(list)
    for a in artifacts:
        grouped[a.folder_number].append(a)

    lines: list[str] = [
        "# Projeto",
        f"> Gerado em: {date.today().isoformat()}",
        "",
        "---",
        "",
    ]
    for week_num in sorted(grouped):
        lines.append(f"## Sprint {sprint_number(week_num)} (Semana {week_num:02d})")
        lines.append("")
        for a in grouped[week_num]:
            lines.append(f"### {a.caption.strip()}")
            lines.append("")
            if a.description_markdown:
                lines.append(a.description_markdown)
                lines.append("")
        lines.append("---")
        lines.append("")

    run_dir = _resolve_run_dir()
    path = run_dir / "projeto.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
