"""V1.2 数据模型包。"""
from .resume_document import (
    Profile,
    ResumeItemMixin,
    EducationItem,
    WorkItem,
    ProjectItem,
    SkillGroup,
    ResumeDocument,
)
from .template_schema import (
    SECTION_TYPES,
)

__all__ = [
    "Profile",
    "ResumeItemMixin",
    "EducationItem",
    "WorkItem",
    "ProjectItem",
    "SkillGroup",
    "ResumeDocument",
    "SECTION_TYPES",
]
