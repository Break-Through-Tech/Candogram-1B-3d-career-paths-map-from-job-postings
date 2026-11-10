"""Retrieve ranked immediate next-job candidates from a selected job node."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.goal_search import tokenize as search_tokenize
from src.job_graph import title_terms


TRANSITION_SCORE_WEIGHTS = {
    "role_similarity": 0.80,
    "title_term_overlap": 0.08,
    "same_civil_service_title": 0.04,
    "same_job_category": 0.03,
    "qualification_overlap": 0.05,
}


@dataclass(frozen=True)
class TransitionPolicy:
    """Rules governing which job moves can be explored."""

    allowed_move_types: frozenset[str] = frozenset(
        {"lateral", "up_one_seniority_rank"}
    )
    use_saved_edges: bool = False


@dataclass(frozen=True)
class NodeTransition:
    """A candidate transition leaving a selected source job."""

    source_job_id: str
    target_job_id: str
    target_business_title: str
    target_career_level: str
    move_type: str
    transition_score: float
    role_similarity: float
    qualification_overlap: float
    shared_job_categories: tuple[str, ...]
    shared_title_terms: tuple[str, ...]
    qualification_gap_terms: tuple[str, ...]
    transition_reason: str

    def as_record(self) -> dict[str, object]:
        """Return the stable transition contract consumed by path search."""
        return {
            "source_job_id": self.source_job_id,
            "target_job_id": self.target_job_id,
            "target_business_title": self.target_business_title,
            "target_career_level": self.target_career_level,
            "move_type": self.move_type,
            "transition_score": self.transition_score,
            "role_similarity": self.role_similarity,
            "qualification_overlap": self.qualification_overlap,
            "shared_job_categories": list(self.shared_job_categories),
            "shared_title_terms": list(self.shared_title_terms),
            "qualification_gap_terms": list(self.qualification_gap_terms),
            "transition_reason": self.transition_reason,
        }


class NodeExplorer:
    """Retrieve immediate candidate moves from an exact selected job ID."""

    def __init__(
        self,
        representations_path: Path = Path(
            "data/processed/job_representations.parquet"
        ),
        edges_path: Path = Path("data/processed/job_move_edges.parquet"),
        policy: TransitionPolicy = TransitionPolicy(),
    ) -> None:
        self._jobs = (
            pd.read_parquet(representations_path)
            .sort_values("Job ID", kind="stable")
            .reset_index(drop=True)
        )
        self._edges = pd.read_parquet(edges_path)
        self._job_ids = set(self._jobs["Job ID"])
        self._jobs_by_id = self._jobs.set_index("Job ID", drop=False)
        self._vectors = np.stack(self._jobs["embedding"]).astype(np.float32)
        self._ranks = self._jobs["seniority_rank"].astype(int).to_numpy()
        self._categories = [
            set(json.loads(value)) for value in self._jobs["job_categories"]
        ]
        self._title_terms = [
            title_terms(str(value)) for value in self._jobs["normalized_title"]
        ]
        self._civil_titles = [
            " ".join(str(value).lower().split())
            for value in self._jobs["Civil Service Title"]
        ]
        self._policy = policy

    def resolve_job(self, job_id: str) -> pd.Series:
        """Return the exact job represented by a selected node ID."""
        if not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("selected job ID must be a non-empty string")

        selected = self._jobs.loc[self._jobs["Job ID"].eq(job_id)]
        if selected.empty:
            raise ValueError("selected job ID is not in the job collection")
        return selected.iloc[0].copy()

    def explore_from_node(
        self,
        selected_job_id: str,
        *,
        limit: int = 5,
    ) -> tuple[NodeTransition, ...]:
        """Return ranked immediate candidate moves from a selected job."""
        if limit < 1:
            raise ValueError("limit must be positive")

        self.resolve_job(selected_job_id)
        outgoing = (
            self._saved_candidates(selected_job_id)
            if self._policy.use_saved_edges
            else self._full_collection_candidates(selected_job_id)
        )

        transitions = []
        for _, edge in outgoing.iterrows():
            target_job_id = edge["target_job_id"]
            if target_job_id not in self._job_ids:
                raise ValueError(
                    f"edge target job ID {target_job_id} is not in the job collection"
                )

            source = self._jobs_by_id.loc[selected_job_id]
            target = self._jobs_by_id.loc[target_job_id]
            qualification_overlap, qualification_gap_terms = (
                self._qualification_evidence(source, target)
            )
            transition_score = self._transition_score(
                edge, qualification_overlap
            )
            shared_categories = tuple(
                json.loads(edge["shared_job_categories"])
                if edge["shared_job_categories"]
                else ()
            )
            shared_title_terms = tuple(
                term
                for term in str(edge["shared_title_terms"]).split(", ")
                if term
            )
            transitions.append(
                NodeTransition(
                    source_job_id=selected_job_id,
                    target_job_id=target_job_id,
                    target_business_title=edge["target_business_title"],
                    target_career_level=edge["target_career_level"],
                    move_type=edge["move_type"],
                    transition_score=transition_score,
                    role_similarity=float(edge["role_similarity"]),
                    qualification_overlap=qualification_overlap,
                    shared_job_categories=shared_categories,
                    shared_title_terms=shared_title_terms,
                    qualification_gap_terms=qualification_gap_terms,
                    transition_reason=self._reason(
                        edge, qualification_overlap, qualification_gap_terms
                    ),
                )
            )
        transitions.sort(
            key=lambda move: (-move.transition_score, move.target_job_id)
        )
        return tuple(transitions[:limit])

    def explore_records(
        self,
        selected_job_id: str,
        *,
        limit: int = 5,
    ) -> tuple[dict[str, object], ...]:
        """Return JSON-friendly transition records for downstream path search."""
        return tuple(
            transition.as_record()
            for transition in self.explore_from_node(selected_job_id, limit=limit)
        )

    def _saved_candidates(self, selected_job_id: str) -> pd.DataFrame:
        return self._edges.loc[
            self._edges["source_job_id"].eq(selected_job_id)
            & self._edges["move_type"].isin(self._policy.allowed_move_types)
        ].sort_values(
            ["ranking_score", "target_job_id"],
            ascending=[False, True],
            kind="stable",
        )

    def _full_collection_candidates(self, selected_job_id: str) -> pd.DataFrame:
        source_index = self._jobs.index[
            self._jobs["Job ID"].eq(selected_job_id)
        ][0]
        source_rank = self._ranks[source_index]
        eligible = np.flatnonzero(
            ((self._ranks == source_rank) | (self._ranks == source_rank + 1))
            & (np.arange(len(self._jobs)) != source_index)
        )
        source_title_terms = self._title_terms[source_index]
        source_categories = self._categories[source_index]
        source_civil_title = self._civil_titles[source_index]
        similarities = self._vectors[eligible] @ self._vectors[source_index]
        rows = []
        for target_index, role_similarity in zip(eligible, similarities):
            target_title_terms = self._title_terms[target_index]
            shared_title_terms = sorted(
                source_title_terms.intersection(target_title_terms)
            )
            shared_categories = sorted(
                source_categories.intersection(self._categories[target_index])
            )
            title_union = source_title_terms | target_title_terms
            title_overlap = (
                len(shared_title_terms) / len(title_union) if title_union else 0.0
            )
            same_civil_service_title = (
                source_civil_title == self._civil_titles[target_index]
            )
            target_rank = self._ranks[target_index]
            move_type = (
                "lateral" if target_rank == source_rank else "up_one_seniority_rank"
            )
            if move_type not in self._policy.allowed_move_types:
                continue
            rows.append(
                {
                    "source_job_id": selected_job_id,
                    "target_job_id": self._jobs.iloc[target_index]["Job ID"],
                    "target_business_title": self._jobs.iloc[target_index][
                        "Business Title"
                    ],
                    "target_career_level": self._jobs.iloc[target_index][
                        "Career Level"
                    ],
                    "move_type": move_type,
                    "role_similarity": float(role_similarity),
                    "title_term_overlap": title_overlap,
                    "same_job_category": bool(shared_categories),
                    "shared_job_categories": json.dumps(
                        shared_categories, ensure_ascii=False
                    ),
                    "same_civil_service_title": same_civil_service_title,
                    "shared_title_terms": ", ".join(shared_title_terms),
                    "ranking_score": float(role_similarity),
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _transition_score(edge: pd.Series, qualification_overlap: float) -> float:
        return sum(
            (
                TRANSITION_SCORE_WEIGHTS["role_similarity"]
                * float(edge["role_similarity"]),
                TRANSITION_SCORE_WEIGHTS["title_term_overlap"]
                * float(edge["title_term_overlap"]),
                TRANSITION_SCORE_WEIGHTS["same_civil_service_title"]
                * float(edge["same_civil_service_title"]),
                TRANSITION_SCORE_WEIGHTS["same_job_category"]
                * float(edge["same_job_category"]),
                TRANSITION_SCORE_WEIGHTS["qualification_overlap"]
                * qualification_overlap,
            )
        )

    @staticmethod
    def _qualification_evidence(
        source: pd.Series, target: pd.Series
    ) -> tuple[float, tuple[str, ...]]:
        source_text = " ".join(
            str(source.get(field, "") or "")
            for field in ("selected_description", "Preferred Skills")
        )
        target_text = " ".join(
            str(target.get(field, "") or "")
            for field in ("Minimum Qual Requirements", "Preferred Skills")
        )
        source_terms = set(search_tokenize(source_text))
        target_terms = set(search_tokenize(target_text))
        if not target_terms:
            return 0.0, ()
        shared_terms = source_terms & target_terms
        overlap = len(shared_terms) / len(target_terms)
        gap_terms = tuple(sorted(target_terms - source_terms))
        return float(overlap), gap_terms

    @staticmethod
    def _reason(
        edge: pd.Series,
        qualification_overlap: float,
        qualification_gap_terms: tuple[str, ...],
    ) -> str:
        reasons = [
            f"{edge['move_type'].replace('_', ' ')} move",
            f"role similarity {float(edge['role_similarity']):.3f}",
            f"qualification evidence {qualification_overlap:.3f}",
        ]
        if edge["shared_title_terms"]:
            reasons.append(f"shared title terms: {edge['shared_title_terms']}")
        if edge["shared_job_categories"]:
            categories = ", ".join(json.loads(edge["shared_job_categories"]))
            reasons.append(f"shared categories: {categories}")
        if qualification_gap_terms:
            reasons.append(
                "qualification terms not evidenced in source: "
                + ", ".join(qualification_gap_terms[:8])
            )
        return "; ".join(reasons)
