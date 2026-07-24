from collections import defaultdict
from datetime import date
from pathlib import Path

from adalove.filters.activity import get_ponderadas
from adalove.models.activity import Activity

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
_UNKNOWN_TURMA = "turma-desconhecida"


def _build_ponderada_cell(activity: Activity) -> str:
    """Only professor, weight, and the card's "Avaliação" tab content — not the
    general description or link, per what's actually relevant for grading.

    Everything lands in one table cell, so newlines (own line breaks plus any
    inside avaliacao_markdown) become <br> and pipes are escaped — a raw
    newline or unescaped | would otherwise break the table row.
    """
    parts = [f"**Título:** {activity.caption.strip()}"]
    if activity.professor_name:
        parts.append(f"**Professor:** {activity.professor_name}")
    parts.append(f"**Peso:** {activity.grade_weight} pontos")
    if activity.avaliacao_markdown:
        parts.append(f"**Descrição:** {activity.avaliacao_markdown}")
    cell = "<br>".join(parts)
    return cell.replace("|", "\\|").replace("\n", "<br>")


def _build_week_section(week_num: int, ponderadas: list[Activity]) -> list[str]:
    lines = [f"## Semana {week_num:02d}", "", "| Ponderadas |", "|---|"]
    for a in ponderadas:
        lines.append(f"| {_build_ponderada_cell(a)} |")
    lines.append("")
    return lines


def write_ponderadas_md(activities: list[Activity], turma: str, output_dir: Path | None = None) -> Path:
    """Write a single <output_dir>/<turma>/ponderadas/ponderadas.md (output_dir
    defaults to OUTPUT_DIR), overwritten on every run.

    One section per week with a table — one row per ponderada, each cell
    holding its título, professor, peso, and descrição. The cross-week
    summary lives at the top of the Calendário material instead, since it's
    weeks the whole module cares about, not just the ones with a ponderada.
    """
    ponderadas = get_ponderadas(activities)

    grouped: dict[int, list[Activity]] = defaultdict(list)
    for a in ponderadas:
        grouped[a.folder_number].append(a)

    ponderadas_dir = (output_dir or OUTPUT_DIR) / (turma or _UNKNOWN_TURMA) / "ponderadas"
    ponderadas_dir.mkdir(parents=True, exist_ok=True)

    lines: list[str] = ["# Ponderadas", f"> Gerado em: {date.today().isoformat()}", "", "---", ""]
    for week_num in sorted(grouped):
        lines.extend(_build_week_section(week_num, grouped[week_num]))

    path = ponderadas_dir / "ponderadas.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
