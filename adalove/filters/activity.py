from collections import Counter

from adalove.config.subjects import AXIS_TO_SUBJECT
from adalove.models.activity import Activity

_NAO_PRESENTE = "Não presente no módulo"


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
