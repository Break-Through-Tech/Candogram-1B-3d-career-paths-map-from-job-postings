"""Embed work profiles and goal queries with an in-memory session cache."""

from types import TracebackType
from typing import Literal, Self

import numpy as np
from google import genai
from google.genai import errors

from src.embedding_config import QUERY_TASK_PREFIX, embed_text
from src.user_profile import GoalQuery, WorkProfile

InputType = Literal["profile", "goal"]


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _clean_items(values: tuple[str, ...]) -> list[str]:
    return sorted(
        {text for value in values if (text := _clean_text(value))},
        key=lambda text: (text.casefold(), text),
    )


def prepare_profile_text(profile: WorkProfile) -> str:
    lines = []
    for label, value in (
        ("Current role", profile.current_role),
        ("Work summary", profile.work_summary),
    ):
        if text := _clean_text(value):
            lines.append(f"{label}: {text}")
    if skills := _clean_items(profile.skills):
        lines.append("Skills: " + ", ".join(skills))
    for experience in profile.experience:
        role = _clean_text(experience.role)
        summary = _clean_text(experience.work_summary)
        if role:
            lines.append(f"Experience role: {role}")
        if summary:
            lines.append(f"Experience work: {summary}")
    if not lines:
        raise ValueError("Profile needs a role, work summary, skills, or experience")
    return QUERY_TASK_PREFIX + "\n".join(lines)


def prepare_goal_text(goal: GoalQuery) -> str:
    text = _clean_text(goal.text)
    if not text:
        raise ValueError("Goal query must not be blank")
    lines = [f"Target work: {text}"]
    if interests := _clean_items(goal.interests):
        lines.append("Interests: " + ", ".join(interests))
    return QUERY_TASK_PREFIX + "\n".join(lines)


class EmbeddingSession:
    """Own one user's cache; the caller owns the Gemini client's lifecycle."""

    def __init__(self, client: genai.Client):
        self._client = client
        self._cache: dict[tuple[InputType, str], np.ndarray] = {}

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.clear()

    def clear(self) -> None:
        self._cache.clear()

    def embed_profile(self, profile: WorkProfile) -> np.ndarray:
        return self._embed("profile", prepare_profile_text(profile))

    def embed_goal(self, goal: GoalQuery) -> np.ndarray:
        return self._embed("goal", prepare_goal_text(goal))

    def _embed(self, input_type: InputType, text: str) -> np.ndarray:
        key = (input_type, text)
        if key not in self._cache:
            try:
                vector = embed_text(self._client, text)
            except errors.APIError as error:
                # Privacy: keep provider error details out of user-session logs.
                raise RuntimeError(
                    f"Gemini embedding request failed (HTTP {error.code})"
                ) from None
            # Callers share the cached array.
            vector.setflags(write=False)
            self._cache[key] = vector
        return self._cache[key]
