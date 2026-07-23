from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from adalove.models.activity import Activity

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


def _build_activity_block(activity: Activity, teacher_subjects: dict[str, str]) -> list[str]:
    lines = [f"#### {activity.caption}"]
    if activity.is_ponderada:
        lines.append("**Ponderada**")
    if activity.professor_name:
        lines.append(f"**Professor:** {activity.professor_name}")
    if activity.url:
        lines.append(f"**URL:** {activity.url}")
    lines.append("")
    if activity.description:
        lines.append(activity.description)
        lines.append("")
    lines.append("---")
    lines.append("")
    return lines


def _build_section(
    activities: list[Activity],
    teacher_subjects: dict[str, str],
) -> list[str]:
    grouped: dict[int, dict[str, list[Activity]]] = defaultdict(lambda: defaultdict(list))
    for a in activities:
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
            lines.append("")
            for activity in grouped[week_num][subject]:
                lines.extend(_build_activity_block(activity, teacher_subjects))
    return lines


def write_activities_md(
    activities: list[Activity],
    teacher_subjects: dict[str, str],
    selected_weeks: list[int],
    selected_subjects: list[str],
) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    run_dir = OUTPUT_DIR / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "activities.md"

    weeks_label = ", ".join(f"Semana {w:02d}" for w in sorted(selected_weeks)) or "Todas"
    subjects_label = ", ".join(sorted(selected_subjects)) or "Todas"
    today = date.today().isoformat()

    lines: list[str] = [
        f"# Adalove — {weeks_label} | {subjects_label}",
        f"> Gerado em: {today}",
        "",
        "---",
        "",
        *_build_section(activities, teacher_subjects),
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
