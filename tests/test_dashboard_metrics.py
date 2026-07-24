import pytest
from datetime import date, timedelta
from adalove.models.dashboard_metrics import DashboardMetrics, _compute_week
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
# All tests use fixed dates (Mon 2026-04-20 as anchor) to avoid day-of-week
# sensitivity. Section starts Wed Apr 22; its Monday is Apr 20.

_MON = date(2026, 4, 20)  # reference Monday


def test_semana_atual_first_day_is_week_1():
    # section starts on the same Monday → week 1
    assert _compute_week("2026-04-20", _today=_MON) == 1


def test_semana_atual_mid_week_same_week_is_1():
    # today is Wed Apr 22 (same calendar week as section start Apr 22)
    assert _compute_week("2026-04-22", _today=date(2026, 4, 22)) == 1


def test_semana_atual_sunday_same_week_is_1():
    # today is Sun Apr 26, section started Mon Apr 20 → still week 1
    assert _compute_week("2026-04-20", _today=date(2026, 4, 26)) == 1


def test_semana_atual_next_monday_is_week_2():
    # today is Mon Apr 27, section started Mon Apr 20 → week 2
    assert _compute_week("2026-04-20", _today=date(2026, 4, 27)) == 2


def test_semana_atual_week_3():
    # today is Mon May 4, section started Mon Apr 20 → week 3
    assert _compute_week("2026-04-20", _today=date(2026, 5, 4)) == 3


def test_semana_atual_week_4_with_real_section_date():
    # real case: sectionDate=2026-04-22 (Wed), today=2026-05-11 (Mon) → week 4
    assert _compute_week("2026-04-22", _today=date(2026, 5, 11)) == 4


def test_semana_atual_empty_date_defaults_to_1():
    assert _compute_week("") == 1


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
        _activity(type=11, grade_weight=0, status=3),
        _activity(type=11, grade_weight=0, status=3),
        _activity(type=11, grade_weight=0, status=1),
    ]
    metrics = DashboardMetrics.from_api(_status(), acts, _section_date(0))
    assert metrics.auto_estudos_feitos == 2


def test_auto_estudos_a_fazer_counts_non_3():
    acts = [
        _activity(type=11, grade_weight=0, status=1),
        _activity(type=11, grade_weight=0, status=2),
        _activity(type=11, grade_weight=0, status=3),
    ]
    metrics = DashboardMetrics.from_api(_status(), acts, _section_date(0))
    assert metrics.auto_estudos_a_fazer == 2


def test_auto_estudos_ignores_other_types():
    acts = [_activity(type=2, status=3), _activity(type=21, status=3)]
    metrics = DashboardMetrics.from_api(_status(), acts, _section_date(0))
    assert metrics.auto_estudos_feitos == 0
    assert metrics.auto_estudos_a_fazer == 0


def test_auto_estudos_excludes_ponderadas():
    """type 11 with a grade weight is a ponderada, not an ungraded autoestudo."""
    acts = [_activity(type=11, grade_weight=3, status=3)]
    metrics = DashboardMetrics.from_api(_status(), acts, _section_date(0))
    assert metrics.auto_estudos_feitos == 0
    assert metrics.auto_estudos_a_fazer == 0


# ── nota_necessaria ───────────────────────────────────────────────────────────

def test_nota_necessaria_no_grades_clamps_to_10():
    # acumulada=0.0 → need = (7.0 - 0.0*0.80) / 0.20 = 35.0 → clamped to 10
    metrics = DashboardMetrics.from_api(_status(done=0.0), [], _section_date(0))
    assert metrics.nota_necessaria == pytest.approx(10.0)


def test_nota_necessaria_with_perfect_grades_clamps_to_0():
    # acumulada=10.0 → need = (7.0 - 10.0*0.80) / 0.20 = -15.0 → clamped to 0
    metrics = DashboardMetrics.from_api(_status(done=10.0), [], _section_date(0))
    assert metrics.nota_necessaria == pytest.approx(0.0)


def test_nota_necessaria_formula():
    # acumulada=6.875 → need = (7.0 - 6.875*0.80) / 0.20 = (7.0 - 5.5) / 0.20 = 7.5
    metrics = DashboardMetrics.from_api(_status(done=6.875), [], _section_date(0))
    assert metrics.nota_necessaria == pytest.approx(7.5)


# ── acumulada / ate_o_momento ─────────────────────────────────────────────────

def test_acumulada_and_ate_o_momento_from_student_status():
    metrics = DashboardMetrics.from_api(_status(done=3.5, result=4.2), [], _section_date(0))
    assert metrics.acumulada == pytest.approx(3.5)
    assert metrics.ate_o_momento == pytest.approx(4.2)
