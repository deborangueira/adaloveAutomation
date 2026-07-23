from dataclasses import dataclass


@dataclass
class SectionInfo:
    section_caption: str
    project_caption: str
    project_description: str
    advisor_name: str
    group_caption: str
    section_date: str

    @classmethod
    def from_api(cls, data: dict) -> "SectionInfo":
        section = data.get("section") or {}
        group = data.get("group") or {}
        return cls(
            section_caption=section.get("sectionCaption") or "",
            project_caption=section.get("projectCaption") or "",
            project_description=section.get("projectDescription") or "",
            advisor_name=section.get("advisorName") or "",
            group_caption=group.get("groupCaption") or "",
            section_date=section.get("sectionDate") or "",
        )
