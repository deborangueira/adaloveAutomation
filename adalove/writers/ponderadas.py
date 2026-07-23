from collections import defaultdict
from datetime import date
from pathlib import Path

from adalove.filters.activity import get_ponderadas
from adalove.models.activity import Activity

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
_UNKNOWN_TURMA = "turma-desconhecida"


def _build_ponderada_block(activity: Activity) -> list[str]:
    """Only professor, weight, and the card's "Avaliação" tab content — not the
    general description or link, per what's actually relevant for grading."""
    lines = [f"### {activity.caption.strip()}"]
    if activity.professor_name:
        lines.append(f"**Professor:** {activity.professor_name}")
    lines.append(f"**Peso:** {activity.grade_weight} pontos")
    lines.append("")
    if activity.avaliacao_markdown:
        lines.append(activity.avaliacao_markdown)
        lines.append("")
    lines.append("---")
    lines.append("")
    return lines


def _build_week_section(week_num: int, ponderadas: list[Activity]) -> list[str]:
    lines = [f"## Semana {week_num:02d}", ""]
    for a in ponderadas:
        lines.extend(_build_ponderada_block(a))
    return lines


def write_ponderadas_md(activities: list[Activity], turma: str) -> list[Path]:
    """Write output/<turma>/ponderadas/, overwritten on every run.

    Produces one file per week that actually has a graded self-study
    (semana-01.md, semana-02.md, ...) — weeks with none are skipped, no
    empty files — plus a single consolidated ponderadas.md with every week
    together.
    """
    ponderadas = get_ponderadas(activities)

    grouped: dict[int, list[Activity]] = defaultdict(list)
    for a in ponderadas:
        grouped[a.folder_number].append(a)

    ponderadas_dir = OUTPUT_DIR / (turma or _UNKNOWN_TURMA) / "ponderadas"
    ponderadas_dir.mkdir(parents=True, exist_ok=True)

    header = ["# Ponderadas", f"> Gerado em: {date.today().isoformat()}", "", "---", ""]
    paths: list[Path] = []

    consolidated: list[str] = list(header)
    for week_num in sorted(grouped):
        section = _build_week_section(week_num, grouped[week_num])
        consolidated.extend(section)

        week_lines = [
            f"# Ponderadas — Semana {week_num:02d}",
            f"> Gerado em: {date.today().isoformat()}",
            "",
            "---",
            "",
            *section,
        ]
        week_path = ponderadas_dir / f"semana-{week_num:02d}.md"
        week_path.write_text("\n".join(week_lines), encoding="utf-8")
        paths.append(week_path)

    consolidated_path = ponderadas_dir / "ponderadas.md"
    consolidated_path.write_text("\n".join(consolidated), encoding="utf-8")
    paths.append(consolidated_path)

    return paths
