"""Embed work profiles and goal queries with an in-memory session cache."""

import hashlib
import json
from dataclasses import dataclass, field
from types import TracebackType
from typing import Literal, Self

import numpy as np
from google import genai
from google.genai import errors, types

from src.embedding_config import (
    EMBEDDING_DIMENSIONS,
    MODEL_MAX_INPUT_TOKENS,
    MODEL_NAME,
)
from src.user_profile import GoalQuery, WorkProfile

TEXT_FORMAT_VERSION = 1
InputType = Literal["profile", "goal"]


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _clean_items(values: tuple[str, ...]) -> list[str]:
    return sorted(
        {text for value in values if (text := _clean_text(value))},
        key=lambda text: (text.casefold(), text),
    )


def prepare_profile_text(profile: WorkProfile) -> str:
    """Select work fields explicitly; leave qualification facts separate."""
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
    return "task: search result | query: " + "\n".join(lines)


def prepare_goal_text(goal: GoalQuery) -> str:
    """Use the query itself as the career goal."""
    text = _clean_text(goal.text)
    if not text:
        raise ValueError("Goal query must not be blank")
    lines = [f"Target work: {text}"]
    if interests := _clean_items(goal.interests):
        lines.append("Interests: " + ", ".join(interests))
    return "task: search result | query: " + "\n".join(lines)


@dataclass(frozen=True)
class UserEmbedding:
    input_type: InputType
    model: str
    dimensions: int
    text_format_version: int
    cache_key: str
    values: tuple[float, ...] = field(repr=False)


class EmbeddingSession:
    """Own one user's cache; the caller owns the Gemini client's lifecycle."""

    def __init__(self, client: genai.Client):
        self._client = client
        self._cache: dict[str, UserEmbedding] = {}

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
        """Discard cached embeddings when the user session ends."""
        self._cache.clear()

    def embed_profile(self, profile: WorkProfile) -> UserEmbedding:
        return self._embed("profile", prepare_profile_text(profile))

    def embed_goal(self, goal: GoalQuery) -> UserEmbedding:
        return self._embed("goal", prepare_goal_text(goal))

    def _embed(self, input_type: InputType, text: str) -> UserEmbedding:
        cache_key = hashlib.sha256(
            json.dumps(
                [
                    input_type,
                    MODEL_NAME,
                    EMBEDDING_DIMENSIONS,
                    TEXT_FORMAT_VERSION,
                    text,
                ],
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # Short UTF-8 inputs fit without a separate token-count request.
            if len(text.encode("utf-8")) > MODEL_MAX_INPUT_TOKENS - 2:
                count = self._client.models.count_tokens(
                    model=MODEL_NAME,
                    contents=text,
                ).total_tokens
                if count is None:
                    raise ValueError("Gemini returned no input token count")
                if count > MODEL_MAX_INPUT_TOKENS:
                    raise ValueError(
                        f"Embedding input exceeds {MODEL_MAX_INPUT_TOKENS} tokens"
                    )
            response = self._client.models.embed_content(
                model=MODEL_NAME,
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=EMBEDDING_DIMENSIONS,
                ),
            )
        except errors.APIError as error:
            raise RuntimeError(
                f"Gemini embedding request failed (HTTP {error.code})"
            ) from None

        if not response.embeddings or len(response.embeddings) != 1:
            raise ValueError("Gemini must return one embedding per input")
        embedding = response.embeddings[0]
        if embedding.statistics and embedding.statistics.truncated:
            raise ValueError("Gemini truncated the embedding input")
        vector = np.asarray(embedding.values, dtype=np.float32)
        if vector.shape != (EMBEDDING_DIMENSIONS,) or not np.isfinite(vector).all():
            raise ValueError("Gemini returned an invalid embedding vector")
        norm = np.linalg.norm(vector)
        if not np.isfinite(norm) or norm == 0:
            raise ValueError("Gemini returned an invalid embedding norm")
        result = UserEmbedding(
            input_type=input_type,
            model=MODEL_NAME,
            dimensions=EMBEDDING_DIMENSIONS,
            text_format_version=TEXT_FORMAT_VERSION,
            cache_key=cache_key,
            values=tuple((vector / norm).tolist()),
        )
        self._cache[cache_key] = result
        return result
