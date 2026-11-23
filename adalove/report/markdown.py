"""Structured report data (report/model.py) → Markdown exports.

These are what each dashboard tab's "Exportar dados" button downloads; the
dashboard embeds them pre-rendered, so the format is defined (and tested)
only here.
"""

from datetime import date

from adalove.config.subjects import SUBJECT_COLORS
from adalove.models.activity import Activity
from adalove.models.section_info import SectionInfo
from adalove.report.model import build_prova, build_report

_BAR_WIDTH = 10
_BLOCK = "█"


def _header(title: str, generated_at: str) -> list[str]:
    return [f"# {title}", f"> Gerado em: {generated_at}", "", "---", ""]


def _colored(label: str) -> str:
    color = SUBJECT_COLORS.get(label)
    return f'_<span style="color:{color}">{label}</span>_' if color else f"_{label}_"


def _blocks(subject: str, fraction: float) -> str:
    """Approximate on purpose (rounded block counts, no percentages) — a
    quick visual read of how the week's aulas split, not a measurement."""
    blocks = _BLOCK * max(1, round(fraction * _BAR_WIDTH))
    color = SUBJECT_COLORS.get(subject)
    return f'<span style="color:{color}">{blocks}</span>' if color else blocks


def render_calendario(report: dict) -> str:
    resumo = report["resumo"]
    headers = [""] + [f"Semana {w['week']:02d}" for w in resumo]
    lines = _header("Calendário", report["generatedAt"])
    lines += [
        "## Resumo do Módulo",
        "",
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
        "| **Ponderadas** | " + " | ".join(", ".join(_colored(s) for s in w["ponderadasSubjects"]) for w in resumo) + " |",
        "| **Composição de aulas** | "
        + " | ".join("".join(_blocks(seg["subject"], seg["fraction"]) for seg in w["composicao"]) for w in resumo)
        + " |",
        "| **Artefatos** | " + " | ".join(str(w["artifactCount"]) if w["artifactCount"] else "" for w in resumo) + " |",
        "",
    ]

    for sprint in report["sprints"]:
        lines += [f"## Sprint {sprint['number']}", ""]
        for item in sprint["encontros"]:
            if item["label"]:
                lines.append(f"- **{item['date']}** — {_colored(item['label'])} — {item['title']}")
            else:
                lines.append(f"- **{item['date']}** — {item['title']}")
        lines.append("")
        if sprint["ponderadas"]:
            lines += ["**Ponderadas:**", ""]
            for p in sprint["ponderadas"]:
                lines.append(f"- {_colored(p['subject'])} — {p['weight']} pontos — Semana {p['week']:02d}")
            lines.append("")
    return "\n".join(lines)


def render_projeto(report: dict) -> str:
    lines = _header("Projeto", report["generatedAt"])
    for sprint in report["projeto"]:
        lines += [f"## Sprint {sprint['sprint']} (Semana {sprint['week']:02d})", ""]
        for a in sprint["artifacts"]:
            lines += [f"### {a['caption']}", ""]
            if a["descriptionMarkdown"]:
                lines += [a["descriptionMarkdown"], ""]
        lines += ["---", ""]
    return "\n".join(lines)


def _ponderada_cell(item: dict) -> str:
    """Everything lands in one table cell, so line breaks become <br> and
    pipes are escaped — either would otherwise break the table row."""
    parts = [f"**Título:** {item['caption']}"]
    if item["professor"]:
        parts.append(f"**Professor:** {item['professor']}")
    parts.append(f"**Peso:** {item['weight']} pontos")
    if item["avaliacaoMarkdown"]:
        parts.append(f"**Descrição:** {item['avaliacaoMarkdown']}")
    return "<br>".join(parts).replace("|", "\\|").replace("\n", "<br>")


def render_ponderadas(report: dict) -> str:
    lines = _header("Ponderadas", report["generatedAt"])
    for week in report["ponderadas"]:
        lines += [f"## Semana {week['week']:02d}", "", "| Ponderadas |", "|---|"]
        lines += [f"| {_ponderada_cell(item)} |" for item in week["items"]]
        lines.append("")
    return "\n".join(lines)


def render_prova_subject(subject: dict, generated_at: str) -> str:
    lines = [f"# {subject['name']}", "", f"> Gerado em: {generated_at}"]
    if subject["professors"]:
        lines.append(f"> Professor: {', '.join(subject['professors'])}")
    lines.append("")
    if subject["instrucoesBySprint"]:
        lines += ["## Instruções", ""]
        for s in subject["instrucoesBySprint"]:
            lines += [f"### Sprint {s['sprint']}", ""]
            lines += [f"- {t}" for t in s["titles"]]
            lines.append("")
    if subject["autoestudo"]:
        lines += ["## Autoestudo", ""]
        lines += [f"- {t}" for t in subject["autoestudo"]]
        lines.append("")
    if subject["links"]:
        lines += ["## Links", "", *subject["links"], ""]
    if subject["books"]:
        lines += ["## Referências a livros", "", *subject["books"], ""]
    return "\n".join(lines)


def prova_slug(name: str) -> str:
    """File-name slug for a discipline ("Programação" → "programação")."""
    return name.lower().replace(" ", "-")


def render_exports(report: dict) -> dict:
    """Every tab's Markdown export, keyed the way the dashboard looks them up."""
    return {
        "calendario": render_calendario(report),
        "projeto": render_projeto(report),
        "ponderadas": render_ponderadas(report),
        "prova": {s["name"]: render_prova_subject(s, report["generatedAt"]) for s in report["prova"]},
    }


# ── Convenience entry points (activities in, Markdown out) ──────────────────

def _report(activities: list[Activity], teacher_subjects: dict[str, str]) -> dict:
    return build_report(activities, SectionInfo("", "", "", "", "", ""), teacher_subjects)


def calendario_md(activities: list[Activity], teacher_subjects: dict[str, str]) -> str:
    return render_calendario(_report(activities, teacher_subjects))


def projeto_md(activities: list[Activity]) -> str:
    return render_projeto(_report(activities, {}))


def ponderadas_md(activities: list[Activity], teacher_subjects: dict[str, str] | None = None) -> str:
    return render_ponderadas(_report(activities, teacher_subjects or {}))


def prova_md(activities: list[Activity], teacher_subjects: dict[str, str]) -> dict[str, str]:
    """Discipline → Markdown, over every activity given (callers decide the
    week scope; the dashboard uses the first 8 weeks)."""
    generated_at = date.today().isoformat()
    return {s["name"]: render_prova_subject(s, generated_at) for s in build_prova(activities, teacher_subjects)}
