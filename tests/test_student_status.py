import pytest
from adalove.models.student_status import StudentStatus

SAMPLE_DATA = {
    "absencesCount": 270,
    "absencesPercentage": "0.08",
    "doneEvaluationResult": "3.50",
    "evaluationResult": "4.20",
}


def test_from_api_parses_normal_values():
    status = StudentStatus.from_api(SAMPLE_DATA)
    assert status.absences_percentage == pytest.approx(0.08)
    assert status.absences_count == 270
    assert status.done_evaluation_result == pytest.approx(3.50)
    assert status.evaluation_result == pytest.approx(4.20)


def test_from_api_null_fields_default_to_zero():
    status = StudentStatus.from_api({})
    assert status.absences_percentage == 0.0
    assert status.absences_count == 0
    assert status.done_evaluation_result == 0.0
    assert status.evaluation_result == 0.0


def test_pie_fraction_normal():
    status = StudentStatus.from_api({"absencesPercentage": "0.08"})
    assert status.pie_fraction == pytest.approx(0.6)


def test_pie_fraction_no_absences():
    status = StudentStatus.from_api({"absencesPercentage": "0.0"})
    assert status.pie_fraction == pytest.approx(1.0)


def test_pie_fraction_clamped_above_max():
    status = StudentStatus.from_api({"absencesPercentage": "0.25"})
    assert status.pie_fraction == 0.0


def test_absence_remaining_label():
    status = StudentStatus.from_api({"absencesPercentage": "0.08"})
    assert status.absence_remaining_label == "12%"


def test_absence_remaining_label_zero_absences():
    status = StudentStatus.from_api({"absencesPercentage": "0.0"})
    assert status.absence_remaining_label == "20%"
