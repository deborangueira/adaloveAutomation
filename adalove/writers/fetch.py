from collections import defaultdict
from datetime import date
from pathlib import Path

from adalove.models.activity import Activity

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
_UNKNOWN_TURMA = "turma-desconhecida"

MODE_LINK = "link"
MODE_DESCRICAO = "descricao"
MODE_COMPLETO = "completo"
MODES = (MODE_LINK, MODE_DESCRICAO, MODE_COMPLETO)


def _slug(text: str) -> str:
    return text.lower().replace(" ", "-")


def _week_caption(activities: list[Activity], week_num: int) -> str:
    return next(
        (a.folder_caption for a in activities if a.folder_number == week_num),
        f"Semana {week_num:02d}",
    )


def _build_activity_block(activity: Activity, show_link: bool) -> list[str]:
    lines = [f"#### {activity.caption}"]
    if activity.is_ponderada:
        lines.append("**Ponderada**")
    if activity.professor_name:
        lines.append(f"**Professor:** {activity.professor_name}")
    if show_link and activity.url:
        lines.append(f"**Link:** {activity.url}")
    lines.append("")
    if activity.description:
        lines.append(activity.description)
        lines.append("")
    lines.append("---")
    lines.append("")
    return lines


def _build_detail_section(activities: list[Activity], show_link: bool) -> list[str]:
    grouped: dict[int, list[Activity]] = defaultdict(list)
    for a in activities:
        grouped[a.folder_number].append(a)

    lines: list[str] = []
    for week_num in sorted(grouped):
        lines.append(f"## {_week_caption(activities, week_num)}")
        lines.append("")
        for activity in grouped[week_num]:
            lines.extend(_build_activity_block(activity, show_link))
    return lines


def _build_link_list_section(activities: list[Activity]) -> list[str]:
    """Compact "só link" rendering: just a bullet list of markdown links per
    week, no professor/description at all."""
    grouped: dict[int, list[Activity]] = defaultdict(list)
    for a in activities:
        if a.url:
            grouped[a.folder_number].append(a)

    lines: list[str] = []
    for week_num in sorted(grouped):
        lines.append(f"## {_week_caption(activities, week_num)}")
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
    mode: str = MODE_COMPLETO,
) -> list[Path]:
    """Write one output/<turma>/buscar/<disciplina>_semana-<semanas>_<modo>.md
    per selected subject — multiple weeks land in the same file, but each
    subject gets its own.

    `mode` controls what each card shows:
      - MODE_LINK: just a link list, no professor/description at all.
      - MODE_DESCRICAO: full card (title, professor, description) without the link.
      - MODE_COMPLETO: full card with the link inline, right under the professor.
    """
    if mode not in MODES:
        raise ValueError(f"mode inválido: {mode!r} (esperado um de {MODES})")

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
        if mode == MODE_LINK:
            body = _build_link_list_section(subject_activities)
        else:
            body = _build_detail_section(subject_activities, show_link=(mode == MODE_COMPLETO))

        lines: list[str] = [
            f"# {subject} — {weeks_label}",
            f"> Gerado em: {today}",
            "",
            "---",
            "",
            *body,
        ]
        path = buscar_dir / f"{_slug(subject)}_semana-{weeks_slug}_{mode}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        paths.append(path)

    return paths
