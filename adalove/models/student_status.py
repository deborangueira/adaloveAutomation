from dataclasses import dataclass

_MAX_ABSENCE = 0.2


@dataclass
class StudentStatus:
    absences_percentage: float
    absences_count: int
    done_evaluation_result: float
    evaluation_result: float

    @property
    def pie_fraction(self) -> float:
        remaining = _MAX_ABSENCE - self.absences_percentage
        return max(0.0, min(1.0, remaining / _MAX_ABSENCE))

    @property
    def absence_remaining_label(self) -> str:
        remaining = max(0.0, _MAX_ABSENCE - self.absences_percentage)
        return f"{round(remaining * 100)}%"

    @classmethod
    def from_api(cls, data: dict) -> "StudentStatus":
        def _float(key: str) -> float:
            val = data.get(key)
            try:
                return float(val) if val is not None else 0.0
            except (ValueError, TypeError):
                return 0.0

        def _int(key: str) -> int:
            val = data.get(key)
            try:
                return int(val) if val is not None else 0
            except (ValueError, TypeError):
                return 0

        return cls(
            absences_percentage=_float("absencesPercentage"),
            absences_count=_int("absencesCount"),
            done_evaluation_result=_float("doneEvaluationResult"),
            evaluation_result=_float("evaluationResult"),
        )
