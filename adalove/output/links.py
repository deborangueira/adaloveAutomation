from collections import defaultdict
from datetime import date
from pathlib import Path

from adalove.models.activity import Activity

OUTPUT_DIR = Path.cwd() / "output"


def _build_section(
    activities: list[Activity],
    teacher_subjects: dict[str, str],
) -> list[str]:
    grouped: dict[int, dict[str, list[Activity]]] = defaultdict(lambda: defaultdict(list))
    for a in activities:
        if not a.url:
            continue
        subject = teacher_subjects.get(a.professor_name, "")
        grouped[a.folder_number][subject].append(a)

    lines: list[str] = []
    for week_num in sorted(grouped):
        week_caption = next(
            (a.folder_caption for a in activities if a.folder_number == week_num),
            f"Semana {week_num:02d}",
        )
        lines.append(f"## {week_caption}")
        lines.append("")
        for subject in sorted(grouped[week_num]):
            lines.append(f"### {subject}")
            for activity in grouped[week_num][subject]:
                suffix = " **(Ponderada)**" if activity.is_ponderada else ""
                lines.append(f"- [{activity.caption}]({activity.url}){suffix}")
            lines.append("")
    return lines


def write_links_md(
    activities: list[Activity],
    teacher_subjects: dict[str, str],
    selected_weeks: list[int],
    selected_subjects: list[str],
) -> Path:
    """Create the file from scratch (first run)."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / "links.md"

    weeks_label = ", ".join(f"Semana {w:02d}" for w in sorted(selected_weeks)) or "Todas"
    subjects_label = ", ".join(sorted(selected_subjects)) or "Todas"
    today = date.today().isoformat()

    lines: list[str] = [
        f"# Links — {weeks_label} | {subjects_label}",
        f"> Gerado em: {today}",
        "",
        *_build_section(activities, teacher_subjects),
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def append_links_md(
    new_activities: list[Activity],
    teacher_subjects: dict[str, str],
) -> Path:
    """Append new links to an existing file under a dated separator."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / "links.md"
    today = date.today().isoformat()

    lines: list[str] = [
        "",
        "---",
        f"> Adicionado em: {today}",
        "",
        *_build_section(new_activities, teacher_subjects),
    ]
    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
