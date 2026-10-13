"""Rank destination-job candidates."""

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.embedding_config import EMBEDDING_DIMENSIONS, MODEL_NAME
from src.profile_embeddings import EmbeddingSession, UserEmbedding
from src.user_profile import GoalQuery, WorkProfile

BM25_K1 = 1.2
BM25_B = 0.75
RRF_K = 60
SEARCH_FIELDS = ("Business Title", "Civil Service Title", "selected_description")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens; keep a trailing `++` or `#` (C++, C#)."""
    return re.findall(r"\w+(?:\+\+|#)?", text.lower())


@dataclass(frozen=True)
class LexicalEvidence:
    field: str
    text: str
    shared_terms: tuple[str, ...]


@dataclass(frozen=True)
class RankedCandidate:
    job_id: str
    business_title: str
    career_level: str
    goal_similarity: float
    lexical_score: float
    fused_score: float
    profile_similarity: float | None
    evidence: tuple[LexicalEvidence, ...]


class GoalSearch:
    def __init__(
        self,
        representations_path: Path = Path("data/processed/job_representations.parquet"),
    ):
        self._jobs = pd.read_parquet(representations_path)
        required = {"job_id", "Career Level", "embedding", "embedding_model"} | set(
            SEARCH_FIELDS
        )
        if missing := required - set(self._jobs.columns):
            raise ValueError(f"Missing job representation fields: {sorted(missing)}")
        self._jobs = self._jobs.sort_values("job_id", kind="stable").reset_index(
            drop=True
        )
        if (
            self._jobs.empty
            or self._jobs["job_id"].isna().any()
            or self._jobs["job_id"].eq("").any()
            or not self._jobs["job_id"].is_unique
        ):
            raise ValueError("Expected nonempty jobs with unique, nonblank IDs")
        if not self._jobs["embedding_model"].eq(MODEL_NAME).all():
            raise ValueError("Job vectors use an incompatible embedding model")
        self._vectors = np.stack(self._jobs["embedding"]).astype(np.float32)
        if (
            self._vectors.shape != (len(self._jobs), EMBEDDING_DIMENSIONS)
            or not np.isfinite(self._vectors).all()
            or not np.allclose(np.linalg.norm(self._vectors, axis=1), 1, atol=1e-5)
        ):
            raise ValueError("Expected valid, normalized job vectors")
        self._fields = self._jobs[list(SEARCH_FIELDS)].fillna("").to_dict("records")
        self._documents = [
            Counter(tokenize("\n".join(fields.values()))) for fields in self._fields
        ]
        self._lengths = np.array([sum(doc.values()) for doc in self._documents])
        self._average_length = max(float(self._lengths.mean()), 1)
        self._document_frequency = Counter(
            term for doc in self._documents for term in doc
        )

    def resolve_job(self, job_id: str) -> pd.Series:
        selected = self._jobs.loc[self._jobs["job_id"].eq(job_id)]
        if selected.empty:
            raise ValueError("Selected job ID is not in the job collection")
        return selected.iloc[0].copy()

    def _similarities(self, embedding: UserEmbedding) -> np.ndarray:
        return self._vectors @ np.asarray(embedding.values, dtype=np.float32)

    def _idf(self, term: str) -> float:
        count = self._document_frequency[term]
        return float(np.log1p((len(self._jobs) - count + 0.5) / (count + 0.5)))

    def _lexical_scores(self, terms: set[str]) -> np.ndarray:
        scores = np.zeros(len(self._jobs))
        length_norm = BM25_K1 * (
            1 - BM25_B + BM25_B * self._lengths / self._average_length
        )
        for term in terms:
            frequency = np.array([doc[term] for doc in self._documents])
            scores += (
                self._idf(term) * frequency * (BM25_K1 + 1) / (frequency + length_norm)
            )
        return scores

    def _evidence(
        self, index: int, terms: set[str], limit: int
    ) -> tuple[LexicalEvidence, ...]:
        found = []
        for field, text in self._fields[index].items():
            passages = (
                re.split(r"(?<=[.!?])\s+|\n+", text)
                if field == "selected_description"
                else [text]
            )
            for passage in passages:
                shared = tuple(sorted(set(tokenize(passage)) & terms))
                if shared:
                    weight = sum(self._idf(term) for term in shared)
                    found.append((weight, LexicalEvidence(field, passage, shared)))
        found.sort(key=lambda item: -item[0])
        return tuple(item[1] for item in found[:limit])

    def rank_candidates(
        self,
        goal: GoalQuery,
        session: EmbeddingSession,
        profile: WorkProfile | None = None,
        *,
        limit: int = 5,
        evidence_limit: int = 3,
    ) -> tuple[RankedCandidate, ...]:
        if limit < 1 or evidence_limit < 0:
            raise ValueError(
                "limit must be positive; evidence_limit cannot be negative"
            )
        terms = set(tokenize(goal.text))
        lexical = self._lexical_scores(terms)
        semantic = self._similarities(session.embed_goal(goal))
        profile_scores = (
            self._similarities(session.embed_profile(profile))
            if profile is not None
            else None
        )

        fused = np.zeros(len(self._jobs))
        rankings = [np.argsort(-semantic, kind="stable")]
        rankings.append(
            np.argsort(-lexical, kind="stable")[: np.count_nonzero(lexical)]
        )
        for order in rankings:
            fused[order] += 1 / (RRF_K + np.arange(1, len(order) + 1))

        tie_break = (
            -profile_scores if profile_scores is not None else np.zeros(len(fused))
        )
        ordered = np.lexsort((tie_break, -fused))[:limit]
        candidates = []
        for index in ordered:
            job = self._jobs.iloc[index]
            candidates.append(
                RankedCandidate(
                    job_id=job["job_id"],
                    business_title=job["Business Title"],
                    career_level=job["Career Level"],
                    goal_similarity=float(semantic[index]),
                    lexical_score=float(lexical[index]),
                    fused_score=float(fused[index]),
                    profile_similarity=float(profile_scores[index])
                    if profile_scores is not None
                    else None,
                    evidence=self._evidence(index, terms, evidence_limit),
                )
            )
        return tuple(candidates)
