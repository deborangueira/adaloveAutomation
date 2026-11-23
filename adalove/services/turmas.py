"""Turma (Adalove "section") selection rules."""

from adalove.api.client import build_section_url, extract_section_uuid
from adalove.models.activity import Activity
from adalove.models.section_info import SectionInfo
from adalove.services.teachers import merge_inferred_teachers


def sort_sections(sections: list[dict]) -> list[dict]:
    """Open turmas first, then most recent first."""
    def key(s: dict) -> tuple[int, int]:
        date_num = int((s.get("date") or "0").replace("-", "") or 0)
        return (0 if s.get("status") == "open" else 1, -date_num)

    return sorted(sections, key=key)


def status_label(section: dict) -> str:
    return "Aberta" if section.get("status") == "open" else "Fechada"


def choice_title(section: dict, current_uuid: str | None) -> str:
    """How a turma reads in a picker: "2026-1A-T17 — Projeto (Aberta) [atual]"."""
    marker = " [atual]" if section.get("uuid") == current_uuid else ""
    return (
        f"{section.get('caption', 'Sem nome')} — {section.get('projectCaption', '')} "
        f"({status_label(section)}){marker}"
    )


def available_turmas(sections: list[dict], config: dict, active_caption: str = "") -> list[dict]:
    """The dashboard's turma switcher entries, sorted, with the active one
    flagged (matched by uuid, or by caption when the uuid isn't known)."""
    current_uuid = extract_section_uuid(config.get("api_url", ""))
    return [
        {
            "uuid": s.get("uuid"),
            "caption": s.get("caption"),
            "projectCaption": s.get("projectCaption"),
            "status": s.get("status"),
            "active": s.get("uuid") == current_uuid or (bool(active_caption) and s.get("caption") == active_caption),
        }
        for s in sort_sections(sections)
    ]


def activate_section(
    config: dict,
    section_uuid: str,
    section: SectionInfo | None = None,
    activities: list[Activity] | None = None,
) -> dict:
    """Point the config at another turma. When that turma's data was loaded,
    also record its name and auto-map any new teacher; when it couldn't be
    loaded, the switch still happens and those fill in on the next load."""
    config["api_url"] = build_section_url(section_uuid)
    if section is not None:
        config["section_caption"] = section.section_caption
    if activities is not None:
        config["teacher_subjects"] = merge_inferred_teachers(config.get("teacher_subjects", {}), activities)
    return config
