import pytest
from datetime import date, timedelta
from adalove.models.dashboard_metrics import DashboardMetrics
from adalove.models.student_status import StudentStatus
from adalove.models.activity import Activity


def _status(done: float = 0.0, result: float = 0.0) -> StudentStatus:
    return StudentStatus(
        absences_percentage=0.0,
        absences_count=0,
        done_evaluation_result=done,
        evaluation_result=result,
    )


def _activity(
    type: int,
    grade_weight: int = 0,
    grade_result: float = -1.0,
    status: int = 1,
    folder_number: int = 1,
) -> Activity:
    return Activity(
        uuid="x",
        caption="Test",
        description="",
        url="",
        professor_name="",
        folder_caption=f"Semana {folder_number:02d}",
        folder_number=folder_number,
        study_type="class",
        status=status,
        tags=[],
        type=type,
        grade_weight=grade_weight,
        grade_result=grade_result,
    )


def _section_date(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


# ── semana_atual ──────────────────────────────────────────────────────────────

def test_semana_atual_first_day_is_week_1():
    metrics = DashboardMetrics.from_api(_status(), [], _section_date(0))
    assert metrics.semana_atual == 1


def test_semana_atual_day_6_is_still_week_1():
    metrics = DashboardMetrics.from_api(_status(), [], _section_date(6))
    assert metrics.semana_atual == 1


def test_semana_atual_day_7_is_week_2():
    metrics = DashboardMetrics.from_api(_status(), [], _section_date(7))
    assert metrics.semana_atual == 2


def test_semana_atual_16_days_is_week_3():
    metrics = DashboardMetrics.from_api(_status(), [], _section_date(16))
    assert metrics.semana_atual == 3


def test_semana_atual_empty_date_defaults_to_1():
    metrics = DashboardMetrics.from_api(_status(), [], "")
    assert metrics.semana_atual == 1


# ── ponderadas_semana ─────────────────────────────────────────────────────────

def test_ponderadas_semana_counts_current_week_only():
    acts = [
        _activity(type=11, grade_weight=3, folder_number=3),  # current
        _activity(type=11, grade_weight=4, folder_number=4),  # future week
        _activity(type=11, grade_weight=0, folder_number=3),  # no weight → excluded
    ]
    metrics = DashboardMetrics.from_api(_status(), acts, _section_date(16))  # week 3
    assert metrics.ponderadas_semana == 1


def test_ponderadas_semana_zero_when_none_this_week():
    acts = [_activity(type=11, grade_weight=3, folder_number=99)]
    metrics = DashboardMetrics.from_api(_status(), acts, _section_date(16))
    assert metrics.ponderadas_semana == 0


# ── auto estudos ──────────────────────────────────────────────────────────────

def test_auto_estudos_feitos_counts_status_3():
    acts = [
        _activity(type=2, status=3),
        _activity(type=2, status=3),
        _activity(type=2, status=1),
    ]
    metrics = DashboardMetrics.from_api(_status(), acts, _section_date(0))
    assert metrics.auto_estudos_feitos == 2


def test_auto_estudos_a_fazer_counts_non_3():
    acts = [
        _activity(type=2, status=1),
        _activity(type=2, status=2),
        _activity(type=2, status=3),
    ]
    metrics = DashboardMetrics.from_api(_status(), acts, _section_date(0))
    assert metrics.auto_estudos_a_fazer == 2


def test_auto_estudos_ignores_other_types():
    acts = [_activity(type=11, status=3), _activity(type=21, status=3)]
    metrics = DashboardMetrics.from_api(_status(), acts, _section_date(0))
    assert metrics.auto_estudos_feitos == 0
    assert metrics.auto_estudos_a_fazer == 0


# ── nota_necessaria ───────────────────────────────────────────────────────────

def test_nota_necessaria_no_grades_clamps_to_10():
    acts = [
        _activity(type=11, grade_weight=4, grade_result=-1.0),
        _activity(type=21, grade_weight=3, grade_result=-1.0),
    ]
    metrics = DashboardMetrics.from_api(_status(), acts, _section_date(0))
    assert metrics.nota_necessaria == pytest.approx(10.0)


def test_nota_necessaria_with_perfect_grades_clamps_to_0():
    # avg_ponderadas=10 → contributes 3.5; avg_artefatos=10 → contributes 4.5; total=8.0 > 7.0
    acts = [
        _activity(type=11, grade_weight=4, grade_result=10.0),
        _activity(type=21, grade_weight=3, grade_result=10.0),
    ]
    metrics = DashboardMetrics.from_api(_status(), acts, _section_date(0))
    assert metrics.nota_necessaria == pytest.approx(0.0)


def test_nota_necessaria_formula():
    # avg_ponderadas = 8.0, avg_artefatos = 6.0
    # need = (7.0 - 8.0*0.35 - 6.0*0.45) / 0.20 = (7.0 - 2.8 - 2.7) / 0.20 = 7.5
    acts = [
        _activity(type=11, grade_weight=1, grade_result=8.0),
        _activity(type=21, grade_weight=1, grade_result=6.0),
    ]
    metrics = DashboardMetrics.from_api(_status(), acts, _section_date(0))
    assert metrics.nota_necessaria == pytest.approx(7.5)


# ── acumulada / ate_o_momento ─────────────────────────────────────────────────

def test_acumulada_and_ate_o_momento_from_student_status():
    metrics = DashboardMetrics.from_api(_status(done=3.5, result=4.2), [], _section_date(0))
    assert metrics.acumulada == pytest.approx(3.5)
    assert metrics.ate_o_momento == pytest.approx(4.2)
