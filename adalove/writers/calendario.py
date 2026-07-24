import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from adalove.config.subjects import SUBJECT_COLORS
from adalove.filters.activity import (
    ENCONTRO_LABELS,
    get_encontros,
    get_ponderadas,
    get_project_artifacts,
    infer_teacher_subjects,
    sprint_number,
)
from adalove.models.activity import Activity

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
_UNKNOWN_TURMA = "turma-desconhecida"
_INSTRUCAO_LABEL = "Instrução"

# The API stores meeting times in UTC, but Adalove's UI displays them 3h
# ahead — confirmed empirically against real cards (e.g. a stored 11:00Z shows
# as 14:00h in the app).
_DISPLAY_OFFSET = timedelta(hours=3)


def _format_date(date_str: str) -> str:
    if not date_str:
        return ""
    # Still apply the display offset even though we only show the date now —
    # a meeting close to UTC midnight could otherwise land on the wrong day.
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")) + _DISPLAY_OFFSET
    return dt.strftime("%d/%m/%Y")


def _colored(label: str) -> str:
    color = SUBJECT_COLORS.get(label)
    if not color:
        return f"_{label}_"
    return f'_<span style="color:{color}">{label}</span>_'


_PLANNING_RE = re.compile(r"planning\s*(\d+)", re.IGNORECASE)
_REVIEW_RE = re.compile(r"review.*?(\d+)", re.IGNORECASE)


def _short_projeto_title(caption: str) -> str:
    """Condense the sprint-cadence titles ("Sprint Planning 2 e Demonstração
    de Aprendizagem") into "Planning2"/"Review2". Titles that don't fit that
    cadence (Workshop, Prova do Módulo) are left as-is."""
    m = _PLANNING_RE.search(caption)
    if m:
        return f"Planning {m.group(1)}"
    m = _REVIEW_RE.search(caption)
    if m:
        return f"Review {m.group(1)}"
    return caption.strip()


_BAR_WIDTH = 10
_BLOCK = "█"


def _colored_blocks(color: str | None, count: int) -> str:
    blocks = _BLOCK * count
    if not color:
        return blocks
    return f'<span style="color:{color}">{blocks}</span>'


def _build_composition_bar(week_instrucao: list[Activity], subjects_by_teacher: dict[str, str]) -> str:
    """Proportional bar of colored blocks — how that week's aulas de
    instrução split across disciplines, same colors as everywhere else.
    Segments follow the chronological order the aulas happened that week
    (first discipline taught first), not alphabetical. Approximate on
    purpose (rounded block counts, no percentages) — it's a quick visual
    read, not a precise measurement."""
    if not week_instrucao:
        return ""
    counts: dict[str, int] = defaultdict(int)
    first_seen: dict[str, str] = {}
    for a in sorted(week_instrucao, key=lambda a: a.date):
        subject = subjects_by_teacher.get(a.professor_name, "") or a.professor_name
        counts[subject] += 1
        first_seen.setdefault(subject, a.date)
    total = sum(counts.values())
    ordered_subjects = sorted(counts, key=lambda s: first_seen[s])
    return "".join(
        _colored_blocks(SUBJECT_COLORS.get(subject), max(1, round(counts[subject] / total * _BAR_WIDTH)))
        for subject in ordered_subjects
    )


def _build_resumo_modulo(
    activities: list[Activity],
    encontros: list[Activity],
    ponderadas: list[Activity],
    artifacts: list[Activity],
    subjects_by_teacher: dict[str, str],
) -> list[str]:
    """Three data rows, one column per week in the module — including weeks
    with no ponderada, aula, or artefato at all: the ponderadas summary
    (disciplines with a ponderada that week, empty if none), a composition
    bar of that week's aulas de instrução split by discipline, and the count
    of project artifacts due that week (only ever even weeks, per the sprint
    deliverable cadence). Empty cells just mean nothing happened that week —
    no need to spell that out with a placeholder."""
    ponderadas_by_week: dict[int, list[Activity]] = defaultdict(list)
    for a in ponderadas:
        ponderadas_by_week[a.folder_number].append(a)

    instrucao_by_week: dict[int, list[Activity]] = defaultdict(list)
    for a in encontros:
        if ENCONTRO_LABELS.get(a.type) == _INSTRUCAO_LABEL:
            instrucao_by_week[a.folder_number].append(a)

    artifacts_by_week: dict[int, list[Activity]] = defaultdict(list)
    for a in artifacts:
        artifacts_by_week[a.folder_number].append(a)

    week_nums = sorted({a.folder_number for a in activities})
    headers = [""] + [f"Semana {w:02d}" for w in week_nums]
    header_row = "| " + " | ".join(headers) + " |"
    sep_row = "|" + "|".join(["---"] * len(headers)) + "|"

    ponderadas_cells = []
    for w in week_nums:
        week_ponderadas = ponderadas_by_week.get(w, [])
        if not week_ponderadas:
            ponderadas_cells.append("")
            continue
        subjects = sorted({
            subjects_by_teacher.get(a.professor_name, "") or a.professor_name
            for a in week_ponderadas
        })
        ponderadas_cells.append(", ".join(_colored(s) for s in subjects))
    ponderadas_row = "| **Ponderadas** | " + " | ".join(ponderadas_cells) + " |"

    composicao_cells = [
        _build_composition_bar(instrucao_by_week.get(w, []), subjects_by_teacher) for w in week_nums
    ]
    composicao_row = "| **Composição de aulas** | " + " | ".join(composicao_cells) + " |"

    artifacts_cells = [str(len(artifacts_by_week[w])) if artifacts_by_week.get(w) else "" for w in week_nums]
    artifacts_row = "| **Artefatos** | " + " | ".join(artifacts_cells) + " |"

    return [
        "## Resumo do Módulo",
        "",
        header_row,
        sep_row,
        ponderadas_row,
        composicao_row,
        artifacts_row,
        "",
    ]


def write_calendario_md(
    activities: list[Activity],
    turma: str,
    teacher_subjects: dict[str, str],
    output_dir: Path | None = None,
) -> Path:
    """Write a single <output_dir>/<turma>/calendario.md (output_dir defaults
    to OUTPUT_DIR), grouped by sprint (each spanning two weeks) — overwritten
    on every run.

    Starts with a per-week module summary table covering every week, even
    the ones with no ponderada, aula, or artefato: a ponderadas row, a
    composition bar of that week's aulas de instrução by discipline, and a
    count of project artifacts due that week. "Instrução" meetings show the
    discipline directly (Programação, UX, ...), each with its own fixed
    color; "Projeto" meetings aren't tied to one discipline, so they keep the
    plain "Projeto" label. Each sprint's ponderadas are listed right below
    its meetings.
    """
    encontros = get_encontros(activities)
    ponderadas = get_ponderadas(activities)
    artifacts = get_project_artifacts(activities)

    # Saved mapping wins; axis-inferred fills in anything not yet configured
    # (same precedence used elsewhere, e.g. turma_info()).
    subjects_by_teacher = {**infer_teacher_subjects(activities), **teacher_subjects}

    encontros_by_sprint: dict[int, list[Activity]] = defaultdict(list)
    for a in encontros:
        encontros_by_sprint[sprint_number(a.folder_number)].append(a)

    ponderadas_by_sprint: dict[int, list[Activity]] = defaultdict(list)
    for a in ponderadas:
        ponderadas_by_sprint[sprint_number(a.folder_number)].append(a)

    all_sprints = sorted(set(encontros_by_sprint) | set(ponderadas_by_sprint))

    turma_dir = (output_dir or OUTPUT_DIR) / (turma or _UNKNOWN_TURMA)
    turma_dir.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Calendário",
        f"> Gerado em: {date.today().isoformat()}",
        "",
        "---",
        "",
    ]
    lines.extend(_build_resumo_modulo(activities, encontros, ponderadas, artifacts, subjects_by_teacher))
    for sprint in all_sprints:
        lines.append(f"## Sprint {sprint}")
        lines.append("")
        for a in encontros_by_sprint.get(sprint, []):
            tipo = ENCONTRO_LABELS.get(a.type, "")
            if tipo == _INSTRUCAO_LABEL:
                subject = subjects_by_teacher.get(a.professor_name, "")
                label = _colored(subject) if subject else _colored(tipo)
                title = a.caption.strip()
                lines.append(f"- **{_format_date(a.date)}** — {label} — {title}")
            else:
                title = _short_projeto_title(a.caption)
                lines.append(f"- **{_format_date(a.date)}** — {title}")
        lines.append("")

        sprint_ponderadas = ponderadas_by_sprint.get(sprint, [])
        if sprint_ponderadas:
            lines.append("**Ponderadas:**")
            lines.append("")
            for a in sprint_ponderadas:
                subject = subjects_by_teacher.get(a.professor_name, "") or a.professor_name
                lines.append(f"- {_colored(subject)} — {a.grade_weight} pontos — Semana {a.folder_number:02d}")
            lines.append("")

    path = turma_dir / "calendario.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
