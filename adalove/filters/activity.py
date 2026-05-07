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
