from dataclasses import dataclass
from datetime import date, timedelta

from adalove.filters.activity import get_autoestudos, get_ponderadas
from adalove.models.activity import Activity
from adalove.models.student_status import StudentStatus

_PASSING_GRADE = 7.0
_PROVA_SHARE = 0.20


@dataclass
class DashboardMetrics:
    acumulada: float
    ate_o_momento: float
    nota_necessaria: float
    semana_atual: int
    ponderadas_semana: int
    auto_estudos_feitos: int
    auto_estudos_a_fazer: int

    @classmethod
    def from_api(
        cls,
        student_status: StudentStatus,
        activities: list[Activity],
        section_date_str: str,
    ) -> "DashboardMetrics":
        semana_atual = _compute_week(section_date_str)
        ponderadas = get_ponderadas(activities)
        artefatos = [a for a in activities if a.type == 21]
        auto_estudos = get_autoestudos(activities)

        acumulada = student_status.done_evaluation_result
        nota_necessaria = (_PASSING_GRADE - acumulada * (1 - _PROVA_SHARE)) / _PROVA_SHARE
        nota_necessaria = max(0.0, min(10.0, nota_necessaria))

        return cls(
            acumulada=acumulada,
            ate_o_momento=student_status.evaluation_result,
            nota_necessaria=round(nota_necessaria, 2),
            semana_atual=semana_atual,
            ponderadas_semana=sum(
                1 for a in ponderadas if a.folder_number == semana_atual
            ),
            auto_estudos_feitos=sum(1 for a in auto_estudos if a.status == 3),
            auto_estudos_a_fazer=sum(1 for a in auto_estudos if a.status != 3),
        )


def _compute_week(section_date_str: str, _today: date | None = None) -> int:
    if not section_date_str:
        return 1
    try:
        section = date.fromisoformat(section_date_str)
    except ValueError:
        return 1
    today = _today or date.today()
    section_monday = section - timedelta(days=section.weekday())
    today_monday = today - timedelta(days=today.weekday())
    return max(1, (today_monday - section_monday).days // 7 + 1)


def _weighted_avg(activities: list[Activity]) -> float:
    graded = [a for a in activities if a.grade_result >= 0]
    if not graded:
        return 0.0
    total_weight = sum(a.grade_weight for a in graded)
    if total_weight == 0:
        return 0.0
    return sum(a.grade_result * a.grade_weight for a in graded) / total_weight
