from collections import defaultdict
from datetime import date
from pathlib import Path

from adalove.models.activity import Activity

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
_UNKNOWN_TURMA = "turma-desconhecida"


def _slug(text: str) -> str:
    return text.lower().replace(" ", "-")


def _build_activity_block(activity: Activity) -> list[str]:
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


def _week_caption(activities: list[Activity], week_num: int) -> str:
    return next(
        (a.folder_caption for a in activities if a.folder_number == week_num),
        f"Semana {week_num:02d}",
    )


def _build_detail_section(activities: list[Activity]) -> list[str]:
    grouped: dict[int, list[Activity]] = defaultdict(list)
    for a in activities:
        grouped[a.folder_number].append(a)

    lines: list[str] = []
    for week_num in sorted(grouped):
        lines.append(f"## {_week_caption(activities, week_num)}")
        lines.append("")
        for activity in grouped[week_num]:
            lines.extend(_build_activity_block(activity))
    return lines


def _build_links_section(activities: list[Activity]) -> list[str]:
    grouped: dict[int, list[Activity]] = defaultdict(list)
    for a in activities:
        if a.url:
            grouped[a.folder_number].append(a)

    lines: list[str] = ["## Links", ""]
    for week_num in sorted(grouped):
        lines.append(f"### {_week_caption(activities, week_num)}")
        lines.append("")
        for activity in grouped[week_num]:
            suffix = " **(Ponderada)**" if activity.is_ponderada else ""
            lines.append(f"- [{activity.caption}]({activity.url}){suffix}")
        lines.append("")
    return lines


def write_fetch_md(
    activities: list[Activity],
    teacher_subjects: dict[str, str],
    selected_weeks: list[int],
    selected_subjects: list[str],
    turma: str,
) -> list[Path]:
    """Write one output/<turma>/buscar/<disciplina>_semana-<semanas>.md per
    selected subject — multiple weeks land in the same file, but each subject
    gets its own, e.g. selecting Programação + Matemática for weeks 1-3 yields
    programação_semana-01-02-03.md and matemática_semana-01-02-03.md.
    """
    weeks_label = ", ".join(f"Semana {w:02d}" for w in sorted(selected_weeks)) or "Todas"
    weeks_slug = "-".join(f"{w:02d}" for w in sorted(selected_weeks)) or "todas"
    today = date.today().isoformat()

    by_subject: dict[str, list[Activity]] = defaultdict(list)
    for a in activities:
        subject = teacher_subjects.get(a.professor_name, "")
        if subject:
            by_subject[subject].append(a)

    buscar_dir = OUTPUT_DIR / (turma or _UNKNOWN_TURMA) / "buscar"
    buscar_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for subject in sorted(by_subject):
        subject_activities = by_subject[subject]
        lines: list[str] = [
            f"# {subject} — {weeks_label}",
            f"> Gerado em: {today}",
            "",
            "---",
            "",
            *_build_detail_section(subject_activities),
            *_build_links_section(subject_activities),
        ]
        path = buscar_dir / f"{_slug(subject)}_semana-{weeks_slug}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        paths.append(path)

    return paths
