"""Activities → structured report data (plain dicts/lists, JSON-ready).

No presentation here: the dashboard (writers/html.py) and the Markdown
exports (report/markdown.py) both render from these structures, so the
rules for what goes in each section live in exactly one place.
"""

from collections import defaultdict
from datetime import date

from adalove.filters.activity import (
    ENCONTRO_LABELS,
    get_autoestudos,
    get_encontros,
    get_ponderadas,
    get_project_artifacts,
    sprint_number,
)
from adalove.models.activity import Activity
from adalove.models.section_info import SectionInfo
from adalove.report.common import (
    INSTRUCAO_LABEL,
    NAO_PRESENTE,
    PROVA_WEEKS,
    UNKNOWN_TURMA,
    format_date,
    is_book_ref,
    is_excluded_url,
    resolve_subjects,
    short_projeto_title,
)

# Adalove's "Autoestudo" card category — see filters/activity.py.
_AUTOESTUDO_TYPE = 11


def build_resumo(
    activities: list[Activity],
    encontros: list[Activity],
    ponderadas: list[Activity],
    artifacts: list[Activity],
    subjects_by_teacher: dict[str, str],
) -> list[dict]:
    """One entry per week of the module — including weeks with nothing in
    them: which disciplines have a ponderada, how that week's aulas de
    instrução split across disciplines (in the order they were taught), and
    how many project artifacts are due."""
    ponderadas_by_week: dict[int, list[Activity]] = defaultdict(list)
    for a in ponderadas:
        ponderadas_by_week[a.folder_number].append(a)

    instrucao_by_week: dict[int, list[Activity]] = defaultdict(list)
    for a in encontros:
        if ENCONTRO_LABELS.get(a.type) == INSTRUCAO_LABEL:
            instrucao_by_week[a.folder_number].append(a)

    artifacts_by_week: dict[int, list[Activity]] = defaultdict(list)
    for a in artifacts:
        artifacts_by_week[a.folder_number].append(a)

    weeks = []
    for w in sorted({a.folder_number for a in activities}):
        ponderadas_subjects = sorted({
            subjects_by_teacher.get(a.professor_name, "") or a.professor_name
            for a in ponderadas_by_week.get(w, [])
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


def _autoestudos_by_encontro(activities: list[Activity]) -> dict[int, dict[str, list[dict]]]:
    """Attach each ungraded autoestudo to the encontro right before it in the
    week's card order (Adalove's `sort`), split into web links and books.
    Keyed by id() of the encontro Activity."""
    attached: dict[int, dict[str, list[dict]]] = defaultdict(lambda: {"autoestudos": [], "books": []})
    by_week: dict[int, list[Activity]] = defaultdict(list)
    for a in activities:
        by_week[a.folder_number].append(a)

    for week_acts in by_week.values():
        current: Activity | None = None
        for a in sorted(week_acts, key=lambda a: getattr(a, "sort", 0) or 0):
            if a.type in ENCONTRO_LABELS:
                current = a
            elif a.type == _AUTOESTUDO_TYPE and a.grade_weight <= 0 and current is not None:
                item = {"title": a.caption.strip(), "url": a.url.strip()}
                attached[id(current)]["books" if is_book_ref(a.url) else "autoestudos"].append(item)
    return attached


def build_sprints(
    encontros: list[Activity],
    ponderadas: list[Activity],
    subjects_by_teacher: dict[str, str],
    activities: list[Activity] | None = None,
) -> list[dict]:
    """The calendar grouped by sprint: each encontro (with its autoestudos)
    and the sprint's ponderadas."""
    attached = _autoestudos_by_encontro(activities) if activities else defaultdict(
        lambda: {"autoestudos": [], "books": []}
    )

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
            extras = attached[id(a)]
            if ENCONTRO_LABELS.get(a.type, "") == INSTRUCAO_LABEL:
                # "Instrução" shows its discipline; "Projeto" meetings aren't
                # tied to one, so they get a condensed title and no label.
                subject = subjects_by_teacher.get(a.professor_name, "")
                subject_field, label, title = subject or None, subject or INSTRUCAO_LABEL, a.caption.strip()
            else:
                subject_field, label, title = None, None, short_projeto_title(a.caption)
            items.append({
                "date": format_date(a.date),
                "week": a.folder_number,
                "subject": subject_field,
                "label": label,
                "title": title,
                "autoestudos": extras["autoestudos"],
                "books": extras["books"],
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


def build_projeto(artifacts: list[Activity]) -> list[dict]:
    """Project deliverables grouped by the (even) week they're due."""
    grouped: dict[int, list[Activity]] = defaultdict(list)
    for a in artifacts:
        grouped[a.folder_number].append(a)
    return [
        {
            "sprint": sprint_number(week_num),
            "week": week_num,
            "artifacts": [
                {"caption": a.caption.strip(), "descriptionMarkdown": a.description_markdown}
                for a in acts
            ],
        }
        for week_num, acts in sorted(grouped.items())
    ]


def build_prova(activities: list[Activity], teacher_subjects: dict[str, str]) -> list[dict]:
    """Exam material per discipline: instruction titles by sprint, ungraded
    autoestudo titles, and links (web vs books), de-duplicated in order.

    Only trusts the *saved* teacher mapping: an unmapped teacher is left out
    rather than guessed into the wrong discipline's study material."""
    by_subject: dict[str, list[Activity]] = defaultdict(list)
    for a in activities:
        subject = teacher_subjects.get(a.professor_name, "")
        if subject and subject != NAO_PRESENTE:
            by_subject[subject].append(a)

    subjects = []
    for subject, acts in sorted(by_subject.items()):
        instrucoes_by_sprint: dict[int, list[str]] = defaultdict(list)
        for a in acts:
            if a.caption and ENCONTRO_LABELS.get(a.type) == INSTRUCAO_LABEL:
                titles = instrucoes_by_sprint[sprint_number(a.folder_number)]
                if a.caption not in titles:
                    titles.append(a.caption)

        usable = [a.url for a in acts if a.url and not is_excluded_url(a.url)]
        subjects.append({
            "name": subject,
            "professors": sorted({a.professor_name for a in acts if a.professor_name}),
            "instrucoesBySprint": [
                {"sprint": s, "titles": titles} for s, titles in sorted(instrucoes_by_sprint.items())
            ],
            "autoestudo": list(dict.fromkeys(a.caption for a in get_autoestudos(acts) if a.caption)),
            "links": list(dict.fromkeys(u for u in usable if not is_book_ref(u))),
            "books": list(dict.fromkeys(u for u in usable if is_book_ref(u))),
        })
    return subjects


def build_turma_disciplinas(activities: list[Activity], teacher_subjects: dict[str, str]) -> list[dict]:
    """Discipline → professor(s) over the whole module (not just Prova's
    8 weeks) — this is about the module's structure, not exam scope."""
    by_subject: dict[str, set[str]] = defaultdict(set)
    for a in activities:
        subject = teacher_subjects.get(a.professor_name, "")
        if subject and subject != NAO_PRESENTE and a.professor_name:
            by_subject[subject].add(a.professor_name)
    return [{"subject": s, "professors": sorted(p)} for s, p in sorted(by_subject.items())]


def build_ponderadas(ponderadas: list[Activity], subjects_by_teacher: dict[str, str]) -> list[dict]:
    """Graded deliverables grouped by week."""
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
                    "avaliacaoMarkdown": a.avaliacao_markdown,
                }
                for a in acts
            ],
        }
        for week_num, acts in sorted(grouped.items())
    ]


def build_report(
    activities: list[Activity],
    section: SectionInfo,
    teacher_subjects: dict[str, str],
    today: date | None = None,
) -> dict:
    """Every section of the module report, ready to render."""
    encontros = get_encontros(activities)
    ponderadas = get_ponderadas(activities)
    artifacts = get_project_artifacts(activities)
    subjects_by_teacher = resolve_subjects(activities, teacher_subjects)

    return {
        "turma": section.section_caption or UNKNOWN_TURMA,
        "generatedAt": (today or date.today()).isoformat(),
        "turmaInfo": {
            "caption": section.section_caption,
            "moduloCaption": section.project_caption,
            "moduloDescricao": section.project_description,
            "orientador": section.advisor_name,
            "grupo": section.group_caption,
            "dataSessao": section.section_date,
            "disciplinas": build_turma_disciplinas(activities, teacher_subjects),
        },
        "resumo": build_resumo(activities, encontros, ponderadas, artifacts, subjects_by_teacher),
        "sprints": build_sprints(encontros, ponderadas, subjects_by_teacher, activities=activities),
        "projeto": build_projeto(artifacts),
        "prova": build_prova([a for a in activities if a.folder_number in PROVA_WEEKS], teacher_subjects),
        "ponderadas": build_ponderadas(ponderadas, subjects_by_teacher),
    }
