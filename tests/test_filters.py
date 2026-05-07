import pytest
from adalove.models.activity import Activity
from adalove.filters.activity import filter_activities, get_unique_weeks, get_unique_teachers


def make_activity(
    professor="Prof A",
    folder_number=5,
    folder_caption="Semana 05",
    uuid="x",
):
    return Activity(
        uuid=uuid,
        caption="Test",
        description="",
        url="https://example.com",
        professor_name=professor,
        folder_caption=folder_caption,
        folder_number=folder_number,
        study_type="class",
        status=1,
        tags=[],
    )


TEACHER_SUBJECTS = {
    "Prof A": "Programação",
    "Prof B": "Matemática",
    "Prof C": "Não presente no módulo",
}


def test_filter_by_week():
    activities = [
        make_activity(folder_number=5, uuid="1"),
        make_activity(folder_number=6, uuid="2"),
    ]
    result = filter_activities(activities, weeks=[5], subjects=[], teacher_subjects=TEACHER_SUBJECTS)
    assert len(result) == 1
    assert result[0].uuid == "1"


def test_filter_by_subject():
    activities = [
        make_activity(professor="Prof A", uuid="1"),
        make_activity(professor="Prof B", uuid="2"),
    ]
    result = filter_activities(activities, weeks=[], subjects=["Programação"], teacher_subjects=TEACHER_SUBJECTS)
    assert len(result) == 1
    assert result[0].uuid == "1"


def test_filter_excludes_nao_presente():
    activities = [make_activity(professor="Prof C", uuid="1")]
    result = filter_activities(activities, weeks=[], subjects=[], teacher_subjects=TEACHER_SUBJECTS)
    assert len(result) == 0


def test_filter_no_restrictions_returns_all_except_nao_presente():
    activities = [
        make_activity(professor="Prof A", uuid="1"),
        make_activity(professor="Prof B", uuid="2"),
        make_activity(professor="Prof C", uuid="3"),
    ]
    result = filter_activities(activities, weeks=[], subjects=[], teacher_subjects=TEACHER_SUBJECTS)
    assert len(result) == 2


def test_filter_combined_week_and_subject():
    activities = [
        make_activity(professor="Prof A", folder_number=5, uuid="1"),
        make_activity(professor="Prof A", folder_number=6, uuid="2"),
        make_activity(professor="Prof B", folder_number=5, uuid="3"),
    ]
    result = filter_activities(
        activities,
        weeks=[5],
        subjects=["Programação"],
        teacher_subjects=TEACHER_SUBJECTS,
    )
    assert len(result) == 1
    assert result[0].uuid == "1"


def test_get_unique_weeks_sorted():
    activities = [
        make_activity(folder_number=6, folder_caption="Semana 06"),
        make_activity(folder_number=5, folder_caption="Semana 05"),
        make_activity(folder_number=5, folder_caption="Semana 05"),
    ]
    weeks = get_unique_weeks(activities)
    assert weeks == [(5, "Semana 05"), (6, "Semana 06")]


def test_get_unique_teachers_sorted():
    activities = [
        make_activity(professor="Prof B"),
        make_activity(professor="Prof A"),
        make_activity(professor="Prof A"),
    ]
    teachers = get_unique_teachers(activities)
    assert teachers == ["Prof A", "Prof B"]


def test_get_unique_teachers_excludes_empty():
    activities = [
        make_activity(professor="Prof A"),
        make_activity(professor=""),
    ]
    teachers = get_unique_teachers(activities)
    assert teachers == ["Prof A"]
