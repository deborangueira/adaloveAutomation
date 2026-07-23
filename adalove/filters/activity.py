from collections import Counter

from adalove.config.subjects import AXIS_TO_SUBJECT
from adalove.models.activity import Activity

_NAO_PRESENTE = "Não presente no módulo"

# `type` has no name in the API response — 21 was found empirically: it's the
# only value that shows up exclusively on even weeks (the sprint deliverable
# cadence), never on odd ones.
_PROJECT_ARTIFACT_TYPE = 21

# 11 is the "Autoestudo" category shown in the Adalove UI — found empirically,
# since every card whose caption literally says "Autoestudo" turned out to be
# type 11 (though not every type-11 card is captioned that way). Combined with
# gradeWeight > 0 (the UI's "Atividade ponderada: X pontos" badge), this is
# exactly the graded-deliverable self-studies, no more and no less.
_PONDERADA_TYPE = 11


def filter_activities(
    activities: list[Activity],
    weeks: list[int],
    subjects: list[str],
    teacher_subjects: dict[str, str],
) -> list[Activity]:
    result = []
    for activity in activities:
        if weeks and activity.folder_number not in weeks:
            continue
        mapped = teacher_subjects.get(activity.professor_name, _NAO_PRESENTE)
        if mapped == _NAO_PRESENTE:
            continue
        if subjects and mapped not in subjects:
            continue
        result.append(activity)
    return result


def get_unique_weeks(activities: list[Activity]) -> list[tuple[int, str]]:
    seen: dict[int, str] = {}
    for a in activities:
        if a.folder_number not in seen:
            seen[a.folder_number] = a.folder_caption
    return sorted(seen.items())


def get_unique_teachers(activities: list[Activity]) -> list[str]:
    return sorted({a.professor_name for a in activities if a.professor_name})


def infer_teacher_subjects(activities: list[Activity]) -> dict[str, str]:
    """Map each teacher to a subject from their activities' `axisCaption`, via
    AXIS_TO_SUBJECT. Uses each teacher's most common axis, in case of stray
    mismatches. Teachers with no resolvable axis are omitted — callers fall
    back to asking manually for those (e.g. an advisor's "Orientação" role,
    which isn't tied to any activity axis at all).
    """
    axis_counts: dict[str, Counter] = {}
    for a in activities:
        if not a.professor_name or not a.axis_caption:
            continue
        axis_counts.setdefault(a.professor_name, Counter())[a.axis_caption] += 1

    inferred: dict[str, str] = {}
    for teacher, counts in axis_counts.items():
        axis = counts.most_common(1)[0][0]
        subject = AXIS_TO_SUBJECT.get(axis)
        if subject:
            inferred[teacher] = subject
    return inferred


def get_project_artifacts(activities: list[Activity]) -> list[Activity]:
    """Return the project deliverable cards — the ones due every other week
    (Semana 02, 04, 06...), one per sprint's wrap-up."""
    return [a for a in activities if a.type == _PROJECT_ARTIFACT_TYPE]


def sprint_number(folder_number: int) -> int:
    """Semana 02/04/06/08/10 → Sprint 1/2/3/4/5 (delivery lands on the sprint's
    even-numbered review week)."""
    return folder_number // 2


def get_ponderadas(activities: list[Activity]) -> list[Activity]:
    """Return the graded self-study deliverables — Adalove's "Autoestudo"
    category (type 11) that also carries a grade weight."""
    return [a for a in activities if a.type == _PONDERADA_TYPE and a.grade_weight > 0]
