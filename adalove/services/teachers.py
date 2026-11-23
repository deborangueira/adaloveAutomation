"""Teacher → discipline mapping rules."""

from adalove.filters.activity import get_unique_teachers, infer_teacher_subjects
from adalove.models.activity import Activity


def merge_inferred_teachers(teacher_subjects: dict[str, str], activities: list[Activity]) -> dict[str, str]:
    """Add the axis-inferred discipline for teachers not mapped yet; never
    overrides a mapping the user saved."""
    merged = dict(teacher_subjects)
    inferred = infer_teacher_subjects(activities)
    for teacher in get_unique_teachers(activities):
        if teacher not in merged and teacher in inferred:
            merged[teacher] = inferred[teacher]
    return merged


def resolve_teacher_mapping(
    activities: list[Activity], existing: dict[str, str]
) -> tuple[dict[str, str], list[str]]:
    """Map every teacher in `activities`: the saved mapping first, then the
    axis-inferred one. Returns (mapping, teachers still needing a choice)."""
    inferred = infer_teacher_subjects(activities)
    mapping: dict[str, str] = {}
    unmapped: list[str] = []
    for teacher in get_unique_teachers(activities):
        subject = existing.get(teacher) or inferred.get(teacher)
        if subject:
            mapping[teacher] = subject
        else:
            unmapped.append(teacher)
    return mapping, unmapped
