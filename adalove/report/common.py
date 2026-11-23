"""Small domain rules shared by every report builder."""

import re
from datetime import datetime, timedelta

from adalove.filters.activity import infer_teacher_subjects
from adalove.models.activity import Activity

UNKNOWN_TURMA = "turma-desconhecida"
NAO_PRESENTE = "Não presente no módulo"
INSTRUCAO_LABEL = "Instrução"

# The API stores meeting times in UTC, but Adalove's UI displays them 3h
# ahead — confirmed empirically against real cards (e.g. a stored 11:00Z shows
# as 14:00h in the app). Applied even though only the date is shown: a meeting
# close to UTC midnight could otherwise land on the wrong day.
DISPLAY_OFFSET = timedelta(hours=3)

# The Prova material covers the first 8 weeks of the module (what the exam
# assesses), not the whole module.
PROVA_WEEKS = range(1, 9)

_BOOK_KEYWORDS = ("sophia", "minhabiblioteca", "minha-biblioteca", "bibliografiainterativa")
_EXCLUDED_DOMAINS = ("inteli.edu.br",)

_PLANNING_RE = re.compile(r"planning\s*(\d+)", re.IGNORECASE)
_REVIEW_RE = re.compile(r"review.*?(\d+)", re.IGNORECASE)


def format_date(date_str: str) -> str:
    """ISO UTC timestamp → "dd/mm/yyyy" in Adalove's display timezone."""
    if not date_str:
        return ""
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")) + DISPLAY_OFFSET
    return dt.strftime("%d/%m/%Y")


def short_projeto_title(caption: str) -> str:
    """Condense the sprint-cadence titles ("Sprint Planning 2 e Demonstração
    de Aprendizagem") into "Planning 2"/"Review 2". Titles that don't fit that
    cadence (Workshop, Prova do Módulo) are left as-is."""
    m = _PLANNING_RE.search(caption)
    if m:
        return f"Planning {m.group(1)}"
    m = _REVIEW_RE.search(caption)
    if m:
        return f"Review {m.group(1)}"
    return caption.strip()


def is_book_ref(url: str) -> bool:
    """Library/e-book platforms (Sophia, Minha Biblioteca, ...)."""
    lower = url.lower()
    return any(k in lower for k in _BOOK_KEYWORDS)


def is_excluded_url(url: str) -> bool:
    """Inteli's own pages (Adalove itself, internal docs) — never useful as
    study links."""
    lower = url.lower()
    return any(domain in lower for domain in _EXCLUDED_DOMAINS)


def resolve_subjects(activities: list[Activity], teacher_subjects: dict[str, str]) -> dict[str, str]:
    """Teacher → subject, where the saved mapping wins and the axis-inferred
    one fills in anything not configured yet."""
    return {**infer_teacher_subjects(activities), **teacher_subjects}
