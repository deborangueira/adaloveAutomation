import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

from adalove.config.subjects import SUBJECT_COLORS
from adalove.filters.activity import (
    ENCONTRO_LABELS,
    get_autoestudos,
    get_encontros,
    get_ponderadas,
    get_project_artifacts,
    infer_teacher_subjects,
    sprint_number,
)
from adalove.models.activity import Activity
from adalove.models.section_info import SectionInfo

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
_ASSETS_DIR = Path(__file__).parent / "html_assets"
_UNKNOWN_TURMA = "turma-desconhecida"
_INSTRUCAO_LABEL = "Instrução"

# Same empirically-confirmed 3h display offset used in writers/calendario.py.
_DISPLAY_OFFSET = timedelta(hours=3)

_BOOK_KEYWORDS = ("sophia", "minhabiblioteca", "minha-biblioteca", "bibliografiainterativa")
_EXCLUDED_DOMAINS = ("inteli.edu.br",)

# Same first-8-weeks scope cli/main.py's _MODO_PROVA_WEEKS applies before
# calling write_subject_links_md — the Prova tab covers what "Material ›
# Prova" always has (assuntos e links das 8 primeiras semanas), not the whole
# module.
_PROVA_WEEKS = range(1, 9)

_PLANNING_RE = re.compile(r"planning\s*(\d+)", re.IGNORECASE)
_REVIEW_RE = re.compile(r"review.*?(\d+)", re.IGNORECASE)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _format_date(date_str: str) -> str:
    if not date_str:
        return ""
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")) + _DISPLAY_OFFSET
    return dt.strftime("%d/%m/%Y")


def _short_projeto_title(caption: str) -> str:
    m = _PLANNING_RE.search(caption)
    if m:
        return f"Planning {m.group(1)}"
    m = _REVIEW_RE.search(caption)
    if m:
        return f"Review {m.group(1)}"
    return caption.strip()


def _is_book_ref(url: str) -> bool:
    lower = url.lower()
    return any(k in lower for k in _BOOK_KEYWORDS)


def _is_excluded_url(url: str) -> bool:
    lower = url.lower()
    return any(domain in lower for domain in _EXCLUDED_DOMAINS)


def _md_to_html(text: str) -> str:
    """Minimal renderer for the light markdown produced by
    Activity.description_markdown/avaliacao_markdown (bold via **, "- "
    bullets, blank-line paragraphs) — just enough to display that text safely,
    not a general markdown parser. Escapes first, so bold/list markers are the
    only markup that survives into the output HTML."""
    if not text:
        return ""
    blocks = []
    for para in text.split("\n\n"):
        lines = [line for line in para.split("\n") if line.strip()]
        if not lines:
            continue
        if all(line.startswith("- ") for line in lines):
            rendered_items = [_BOLD_RE.sub(r"<strong>\1</strong>", escape(line[2:])) for line in lines]
            items = "".join(f"<li>{item}</li>" for item in rendered_items)
            blocks.append(f"<ul>{items}</ul>")
        else:
            html_line = "<br>".join(_BOLD_RE.sub(r"<strong>\1</strong>", escape(line)) for line in lines)
            blocks.append(f"<p>{html_line}</p>")
    return "".join(blocks)


def _build_resumo(
    activities: list[Activity],
    encontros: list[Activity],
    ponderadas: list[Activity],
    artifacts: list[Activity],
    subjects_by_teacher: dict[str, str],
) -> list[dict]:
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

    weeks = []
    for w in sorted({a.folder_number for a in activities}):
        week_ponderadas = ponderadas_by_week.get(w, [])
        ponderadas_subjects = sorted({
            subjects_by_teacher.get(a.professor_name, "") or a.professor_name for a in week_ponderadas
        })

        counts: dict[str, int] = defaultdict(int)
        first_seen: dict[str, str] = {}
        for a in sorted(instrucao_by_week.get(w, []), key=lambda a: a.date):
            subject = subjects_by_teacher.get(a.professor_name, "") or a.professor_name
            counts[subject] += 1
            first_seen.setdefault(subject, a.date)
        total = sum(counts.values())
        composicao = (
            [{"subject": s, "fraction": counts[s] / total} for s in sorted(counts, key=lambda s: first_seen[s])]
            if total
            else []
        )

        weeks.append({
            "week": w,
            "ponderadasSubjects": ponderadas_subjects,
            "composicao": composicao,
            "artifactCount": len(artifacts_by_week.get(w, [])),
        })
    return weeks


def _build_sprints(
    encontros: list[Activity], ponderadas: list[Activity], subjects_by_teacher: dict[str, str]
) -> list[dict]:
    encontros_by_sprint: dict[int, list[Activity]] = defaultdict(list)
    for a in encontros:
        encontros_by_sprint[sprint_number(a.folder_number)].append(a)

    ponderadas_by_sprint: dict[int, list[Activity]] = defaultdict(list)
    for a in ponderadas:
        ponderadas_by_sprint[sprint_number(a.folder_number)].append(a)

    sprints = []
    for sprint in sorted(set(encontros_by_sprint) | set(ponderadas_by_sprint)):
        items = []
        for a in encontros_by_sprint.get(sprint, []):
            tipo = ENCONTRO_LABELS.get(a.type, "")
            if tipo == _INSTRUCAO_LABEL:
                subject = subjects_by_teacher.get(a.professor_name, "")
                items.append({
                    "date": _format_date(a.date),
                    "week": a.folder_number,
                    "subject": subject or None,
                    "label": subject or tipo,
                    "title": a.caption.strip(),
                })
            else:
                items.append({
                    "date": _format_date(a.date),
                    "week": a.folder_number,
                    "subject": None,
                    "label": None,
                    "title": _short_projeto_title(a.caption),
                })

        sprint_ponderadas = [
            {
                "subject": subjects_by_teacher.get(a.professor_name, "") or a.professor_name,
                "weight": a.grade_weight,
                "week": a.folder_number,
                "title": a.caption.strip(),
            }
            for a in ponderadas_by_sprint.get(sprint, [])
        ]
        sprints.append({"number": sprint, "encontros": items, "ponderadas": sprint_ponderadas})
    return sprints


def _build_projeto(artifacts: list[Activity]) -> list[dict]:
    grouped: dict[int, list[Activity]] = defaultdict(list)
    for a in artifacts:
        grouped[a.folder_number].append(a)

    return [
        {
            "sprint": sprint_number(week_num),
            "week": week_num,
            "artifacts": [
                {
                    "caption": a.caption.strip(),
                    "html": _md_to_html(a.description_markdown),
                    # Raw markdown alongside the rendered HTML — the "Exportar
                    # dados" button rebuilds projeto.md client-side from this,
                    # since the page has no server to call write_project_md.
                    "descriptionMarkdown": a.description_markdown,
                }
                for a in acts
            ],
        }
        for week_num, acts in sorted(grouped.items())
    ]


def _build_prova(activities: list[Activity], teacher_subjects: dict[str, str]) -> list[dict]:
    by_subject: dict[str, list[Activity]] = defaultdict(list)
    for a in activities:
        subject = teacher_subjects.get(a.professor_name, "")
        if subject and subject != "Não presente no módulo":
            by_subject[subject].append(a)

    subjects = []
    for subject, acts in sorted(by_subject.items()):
        professors = sorted({a.professor_name for a in acts if a.professor_name})

        instrucoes_by_sprint: dict[int, list[str]] = defaultdict(list)
        for a in acts:
            if a.caption and ENCONTRO_LABELS.get(a.type) == _INSTRUCAO_LABEL:
                titles = instrucoes_by_sprint[sprint_number(a.folder_number)]
                if a.caption not in titles:
                    titles.append(a.caption)

        autoestudo_titles = list(dict.fromkeys(a.caption for a in get_autoestudos(acts) if a.caption))
        links = list(dict.fromkeys(
            a.url for a in acts if a.url and not _is_book_ref(a.url) and not _is_excluded_url(a.url)
        ))
        books = list(dict.fromkeys(
            a.url for a in acts if a.url and _is_book_ref(a.url) and not _is_excluded_url(a.url)
        ))

        subjects.append({
            "name": subject,
            "professors": professors,
            "instrucoesBySprint": [
                {"sprint": s, "titles": titles} for s, titles in sorted(instrucoes_by_sprint.items())
            ],
            "autoestudo": autoestudo_titles,
            "links": links,
            "books": books,
        })
    return subjects


def _build_turma_disciplinas(activities: list[Activity], teacher_subjects: dict[str, str]) -> list[dict]:
    """Same subject → professor(s) grouping as _build_prova, but over every
    activity (not just the first 8 weeks) — this feeds the Turma tab, which
    is about the module's overall structure, not exam scope."""
    by_subject: dict[str, set[str]] = defaultdict(set)
    for a in activities:
        subject = teacher_subjects.get(a.professor_name, "")
        if subject and subject != "Não presente no módulo" and a.professor_name:
            by_subject[subject].add(a.professor_name)
    return [
        {"subject": subject, "professors": sorted(professors)}
        for subject, professors in sorted(by_subject.items())
    ]


def _build_ponderadas(ponderadas: list[Activity], subjects_by_teacher: dict[str, str]) -> list[dict]:
    grouped: dict[int, list[Activity]] = defaultdict(list)
    for a in ponderadas:
        grouped[a.folder_number].append(a)

    return [
        {
            "week": week_num,
            "items": [
                {
                    "caption": a.caption.strip(),
                    "professor": a.professor_name,
                    "subject": subjects_by_teacher.get(a.professor_name, "") or None,
                    "weight": a.grade_weight,
                    "html": _md_to_html(a.avaliacao_markdown),
                    # Raw markdown for the "Exportar dados" button — see the
                    # matching note in _build_projeto.
                    "avaliacaoMarkdown": a.avaliacao_markdown,
                }
                for a in acts
            ],
        }
        for week_num, acts in sorted(grouped.items())
    ]


def _build_data(
    activities: list[Activity],
    section: SectionInfo,
    teacher_subjects: dict[str, str],
    available_turmas: list[dict] | None = None,
) -> dict:
    encontros = get_encontros(activities)
    ponderadas = get_ponderadas(activities)
    artifacts = get_project_artifacts(activities)

    # Saved mapping wins; axis-inferred fills in anything not yet configured —
    # same precedence as writers/calendario.py. writers/subject_links.py's
    # equivalent (the Prova tab here) only trusts the saved mapping, so that
    # one stays on the raw teacher_subjects param instead.
    subjects_by_teacher = {**infer_teacher_subjects(activities), **teacher_subjects}

    return {
        "turma": section.section_caption or _UNKNOWN_TURMA,
        "generatedAt": date.today().isoformat(),
        "availableTurmas": available_turmas or [],
        "subjectColors": SUBJECT_COLORS,
        "turmaInfo": {
            "caption": section.section_caption,
            "moduloCaption": section.project_caption,
            "moduloDescricao": section.project_description,
            "orientador": section.advisor_name,
            "grupo": section.group_caption,
            "dataSessao": section.section_date,
            "disciplinas": _build_turma_disciplinas(activities, teacher_subjects),
        },
        "resumo": _build_resumo(activities, encontros, ponderadas, artifacts, subjects_by_teacher),
        "sprints": _build_sprints(encontros, ponderadas, subjects_by_teacher),
        "projeto": _build_projeto(artifacts),
        "prova": _build_prova(
            [a for a in activities if a.folder_number in _PROVA_WEEKS], teacher_subjects
        ),
        "ponderadas": _build_ponderadas(ponderadas, subjects_by_teacher),
    }


def write_html_dashboard(
    activities: list[Activity],
    section: SectionInfo,
    teacher_subjects: dict[str, str],
    output_dir: Path | None = None,
    available_turmas: list[dict] | None = None,
) -> Path:
    """Write a single <output_dir>/<turma>/dashboard.html (output_dir defaults
    to OUTPUT_DIR), overwritten on every run — an interactive, self-contained
    (no external assets, works straight off the filesystem) view over the
    same data as the Calendário/Projeto/Prova/Ponderadas Markdown files, with
    tabs, copy-to-clipboard on project artifacts and Prova links, and a
    per-tab "Exportar dados" button that rebuilds that tab's .md file
    client-side and downloads it (the page has no server to call the writer
    functions directly once it's open in a browser).
    """
    data = _build_data(activities, section, teacher_subjects, available_turmas=available_turmas)
    # The JSON sits inside a <script type="application/json"> tag as inert
    # text, parsed via JSON.parse() in JS — never interpreted as markup or
    # code, so a caption containing "</script>" can't break out of the tag or
    # execute. `\/` is a legal JSON escape for `/`, so this is safe wherever
    # it lands in the payload.
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    turma_dir = (output_dir or OUTPUT_DIR) / (section.section_caption or _UNKNOWN_TURMA)
    turma_dir.mkdir(parents=True, exist_ok=True)

    path = turma_dir / "dashboard.html"
    path.write_text(_render_template(data_json), encoding="utf-8")
    return path


def _render_template(data_json: str) -> str:
    """Inline style.css and script.js into template.html — the shipped
    dashboard.html stays a single self-contained file (no external assets,
    works straight off the filesystem); only the source is split up."""
    template = (_ASSETS_DIR / "template.html").read_text(encoding="utf-8")
    style = (_ASSETS_DIR / "style.css").read_text(encoding="utf-8").rstrip("\n")
    script = (_ASSETS_DIR / "script.js").read_text(encoding="utf-8").rstrip("\n")
    return (
        template
        .replace("__STYLE__", style)
        .replace("__SCRIPT__", script)
        .replace("__DATA__", data_json)
    )

