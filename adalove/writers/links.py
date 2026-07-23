from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from adalove.models.activity import Activity

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


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
    stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    run_dir = OUTPUT_DIR / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "links.md"

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
