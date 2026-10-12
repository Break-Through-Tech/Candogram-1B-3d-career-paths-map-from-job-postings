"""Work-related inputs for profile matching and target-role search."""

from dataclasses import dataclass


@dataclass(kw_only=True, repr=False)
class WorkExperience:
    role: str = ""
    work_summary: str = ""
    years: float | None = None


@dataclass(kw_only=True, repr=False)
class WorkProfile:
    current_role: str = ""
    work_summary: str = ""
    skills: tuple[str, ...] = ()
    experience: tuple[WorkExperience, ...] = ()
    education: tuple[str, ...] = ()
    licenses: tuple[str, ...] = ()


@dataclass(kw_only=True, repr=False)
class GoalQuery:
    """A natural-language description of where the user wants to go."""

    text: str
    interests: tuple[str, ...] = ()
