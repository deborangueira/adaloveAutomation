from collections import defaultdict
from datetime import date
from pathlib import Path

from adalove.filters.activity import get_project_artifacts, sprint_number
from adalove.models.activity import Activity

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
_UNKNOWN_TURMA = "turma-desconhecida"


def _build_sprint_section(week_num: int, artifacts: list[Activity]) -> list[str]:
    lines = [f"## Sprint {sprint_number(week_num)} (Semana {week_num:02d})", ""]
    for a in artifacts:
        lines.append(f"### {a.caption.strip()}")
        lines.append("")
        if a.description_markdown:
            lines.append(a.description_markdown)
            lines.append("")
    lines.append("---")
    lines.append("")
    return lines


def write_project_md(activities: list[Activity], turma: str) -> list[Path]:
    """Write output/<turma>/projeto/, overwritten on every run — this is the
    current state of the module's artifacts, not a history of past runs.

    Produces one file per sprint (sprint-1.md, sprint-2.md, ...) plus a single
    consolidated projeto.md with every sprint together.
    """
    artifacts = get_project_artifacts(activities)

    grouped: dict[int, list[Activity]] = defaultdict(list)
    for a in artifacts:
        grouped[a.folder_number].append(a)

    project_dir = OUTPUT_DIR / (turma or _UNKNOWN_TURMA) / "projeto"
    project_dir.mkdir(parents=True, exist_ok=True)

    header = ["# Projeto", f"> Gerado em: {date.today().isoformat()}", "", "---", ""]
    paths: list[Path] = []

    consolidated: list[str] = list(header)
    for week_num in sorted(grouped):
        section = _build_sprint_section(week_num, grouped[week_num])
        consolidated.extend(section)

        sprint_lines = [
            f"# Projeto — Sprint {sprint_number(week_num)}",
            f"> Gerado em: {date.today().isoformat()}",
            "",
            "---",
            "",
            *section,
        ]
        sprint_path = project_dir / f"sprint-{sprint_number(week_num)}.md"
        sprint_path.write_text("\n".join(sprint_lines), encoding="utf-8")
        paths.append(sprint_path)

    consolidated_path = project_dir / "projeto.md"
    consolidated_path.write_text("\n".join(consolidated), encoding="utf-8")
    paths.append(consolidated_path)

    return paths
