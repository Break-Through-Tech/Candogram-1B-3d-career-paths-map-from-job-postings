"""Build job representations and nearby job suggestions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from google import genai

from src.embedding_config import (
    EMBEDDING_DIMENSIONS,
    MODEL_MAX_INPUT_TOKENS,
    MODEL_NAME,
    embed_text,
)

DEFAULT_MAX_CANDIDATES_PER_LEVEL = 32
BROWSING_SCORE_WEIGHTS = {
    "role_similarity": 0.90,
    "title_term_overlap": 0.06,
    "same_civil_service_title": 0.03,
    "same_job_category": 0.01,
}

DISPLAY_FIELDS = {
    "business_title": "Business Title",
    "civil_service_title": "Civil Service Title",
    "job_category": "Job Category",
    "career_level": "Career Level",
}

EDGE_COLUMNS = (
    "edge_id",
    "source_job_id",
    "target_job_id",
    "move_type",
    "source_seniority_rank",
    "target_seniority_rank",
    "role_similarity",
    "title_term_overlap",
    "same_job_category",
    "shared_job_categories",
    "same_civil_service_title",
    "shared_title_terms",
    "ranking_score",
    *(f"{side}_{field}" for field in DISPLAY_FIELDS for side in ("source", "target")),
)

TITLE_STOP_WORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "the",
    "to",
    "with",
}


def value_as_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def load_jobs(input_path: Path) -> pd.DataFrame:
    return pd.read_csv(input_path, dtype={"Job ID": "string"})


def build_role_text(job: pd.Series) -> str:
    return "\n".join(
        (
            f"Business title: {value_as_text(job['Business Title'])}",
            f"Civil service title: {value_as_text(job['Civil Service Title'])}",
            f"Job category: {value_as_text(job['Job Category'])}",
            f"Job description: {value_as_text(job['selected_description'])}",
        )
    )


def load_prepared_descriptions(jobs: pd.DataFrame, path: Path) -> pd.DataFrame:
    prepared = pd.read_csv(path, dtype={"Job ID": "string"}, low_memory=False)
    selected = prepared[
        ["Job ID", "Job Description", "selected_description", "representation_status"]
    ].rename(columns={"Job Description": "prepared_source_description"})
    jobs = jobs.merge(selected, on="Job ID", how="left", validate="one_to_one")
    processed = jobs["representation_status"].notna()
    stale = processed & jobs["prepared_source_description"].ne(jobs["Job Description"])
    if stale.any():
        job_id = jobs.loc[stale, "Job ID"].iloc[0]
        raise ValueError(
            f"Prepared description is stale for Job ID {job_id}; "
            "run src.job_descriptions first"
        )
    jobs["selected_description"] = jobs["selected_description"].fillna(
        jobs["Job Description"]
    )
    jobs["representation_status"] = jobs["representation_status"].fillna(
        "original_fallback"
    )
    jobs = jobs.drop(columns="prepared_source_description")
    return jobs


def load_cached_embeddings(path: Path) -> dict[tuple[str, str], np.ndarray]:
    if not path.exists():
        return {}
    previous = pd.read_parquet(
        path, columns=["Job ID", "semantic_role_text", "embedding_model", "embedding"]
    )
    return {
        (job_id, text): vector
        for job_id, text, model, vector in previous.itertuples(index=False, name=None)
        if model == MODEL_NAME and len(vector) == EMBEDDING_DIMENSIONS
    }


def embed_roles(
    jobs: pd.DataFrame, role_texts: list[str], cached: dict[tuple[str, str], np.ndarray]
) -> np.ndarray:
    client = None
    vectors = []
    new_embeddings = 0
    for index, (job_id, text) in enumerate(zip(jobs["Job ID"], role_texts), start=1):
        vector = cached.get((job_id, text))
        if vector is None:
            if client is None:
                load_dotenv(Path(__file__).resolve().parents[1] / ".env")
                client = genai.Client()
            vector = embed_text(client, text)
            new_embeddings += 1
        vectors.append(vector)
        if index % 100 == 0 or index == len(role_texts):
            print(f"Prepared {index}/{len(role_texts)} jobs", flush=True)
    print(
        f"Reused {len(role_texts) - new_embeddings} embeddings; created {new_embeddings}."
    )
    return np.asarray(vectors, dtype=np.float32)


def title_terms(title: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z0-9]+", title.lower())
        if term not in TITLE_STOP_WORDS
    }


def stable_edge_id(source_job_id: str, target_job_id: str) -> str:
    endpoints = f"{source_job_id}\x1f{target_job_id}".encode()
    return f"move_{hashlib.sha256(endpoints).hexdigest()}"


def normalized_value(value: object) -> str:
    return " ".join(value_as_text(value).lower().split())


def build_edges(
    jobs: pd.DataFrame,
    embeddings: np.ndarray,
    *,
    max_candidates_per_level: int,
) -> pd.DataFrame:
    similarities = embeddings @ embeddings.T
    job_ids = jobs["Job ID"].tolist()
    ranks = jobs["seniority_rank"].astype(int).to_numpy()
    categories = [set(json.loads(value)) for value in jobs["job_categories"]]
    civil_service_titles = [
        normalized_value(value) for value in jobs["Civil Service Title"]
    ]
    title_term_sets = [
        title_terms(value_as_text(value)) for value in jobs["normalized_title"]
    ]
    display = [
        {field: value_as_text(row[column]) for field, column in DISPLAY_FIELDS.items()}
        for row in jobs[list(DISPLAY_FIELDS.values())].to_dict("records")
    ]

    edge_rows: list[dict[str, object]] = []
    for source_index, source_job_id in enumerate(job_ids):
        eligible_indices = np.flatnonzero(
            ((ranks == ranks[source_index]) | (ranks == ranks[source_index] + 1))
            & (np.arange(len(jobs)) != source_index)
        )
        candidates_by_rank = {
            ranks[source_index]: [],
            ranks[source_index] + 1: [],
        }
        for target_index in eligible_indices:
            role_similarity = float(similarities[source_index, target_index])
            shared_terms = sorted(
                title_term_sets[source_index].intersection(
                    title_term_sets[target_index]
                )
            )
            shared_categories = sorted(
                categories[source_index].intersection(categories[target_index])
            )
            same_category = bool(shared_categories)
            same_civil_service_title = (
                civil_service_titles[source_index] == civil_service_titles[target_index]
            )
            title_union = title_term_sets[source_index] | title_term_sets[target_index]
            title_overlap = len(shared_terms) / len(title_union) if title_union else 0.0
            ranking_score = (
                BROWSING_SCORE_WEIGHTS["role_similarity"] * role_similarity
                + BROWSING_SCORE_WEIGHTS["title_term_overlap"] * title_overlap
                + BROWSING_SCORE_WEIGHTS["same_civil_service_title"]
                * float(same_civil_service_title)
                + BROWSING_SCORE_WEIGHTS["same_job_category"] * float(same_category)
            )
            candidates_by_rank[ranks[target_index]].append(
                (
                    target_index,
                    {
                        "role_similarity": role_similarity,
                        "title_term_overlap": title_overlap,
                        "same_job_category": same_category,
                        "shared_job_categories": json.dumps(
                            shared_categories, ensure_ascii=False
                        ),
                        "same_civil_service_title": same_civil_service_title,
                        "shared_title_terms": ", ".join(shared_terms),
                        "ranking_score": ranking_score,
                    },
                )
            )

        for candidates in candidates_by_rank.values():
            candidates.sort(
                key=lambda candidate: (
                    -candidate[1]["ranking_score"],
                    job_ids[candidate[0]],
                )
            )
            for target_index, scores in candidates[:max_candidates_per_level]:
                target_job_id = job_ids[target_index]
                edge_rows.append(
                    {
                        **scores,
                        "edge_id": stable_edge_id(source_job_id, target_job_id),
                        "source_job_id": source_job_id,
                        "target_job_id": target_job_id,
                        "move_type": (
                            "lateral"
                            if ranks[target_index] == ranks[source_index]
                            else "up_one_seniority_rank"
                        ),
                        "source_seniority_rank": int(ranks[source_index]),
                        "target_seniority_rank": int(ranks[target_index]),
                        **{f"source_{k}": v for k, v in display[source_index].items()},
                        **{f"target_{k}": v for k, v in display[target_index].items()},
                    }
                )

    edges = pd.DataFrame(edge_rows, columns=EDGE_COLUMNS)
    return edges.sort_values(
        ["source_job_id", "ranking_score", "target_job_id"],
        ascending=[True, False, True],
        kind="stable",
    ).reset_index(drop=True)


def build_job_graph(
    input_path: Path,
    representations_path: Path,
    edges_path: Path,
    metadata_path: Path,
    *,
    prepared_path: Path = Path("data/processed/description_full/prepared_jobs.csv"),
    max_candidates_per_level: int = DEFAULT_MAX_CANDIDATES_PER_LEVEL,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if max_candidates_per_level < 1:
        raise ValueError("max_candidates_per_level must be at least 1")

    jobs = load_prepared_descriptions(load_jobs(input_path), prepared_path)
    role_texts = [build_role_text(job) for _, job in jobs.iterrows()]
    embeddings = embed_roles(
        jobs, role_texts, load_cached_embeddings(representations_path)
    )
    representations = jobs.assign(
        semantic_role_text=role_texts,
        embedding_model=MODEL_NAME,
        embedding=list(embeddings),
    )

    edges = build_edges(
        jobs,
        embeddings,
        max_candidates_per_level=max_candidates_per_level,
    )
    input_digest = hashlib.sha256(input_path.read_bytes()).hexdigest()
    metadata = {
        "schema_version": 7,
        "input_csv": str(input_path),
        "input_sha256": input_digest,
        "job_count": len(jobs),
        "embedding_model": MODEL_NAME,
        "description_selection": {
            "source": str(prepared_path),
            "extracted": int(jobs["representation_status"].eq("extracted").sum()),
            "original_fallback": int(
                jobs["representation_status"].eq("original_fallback").sum()
            ),
        },
        "representation": {
            "model_token_limit": MODEL_MAX_INPUT_TOKENS,
            "embedding_dimensions": EMBEDDING_DIMENSIONS,
        },
        "edge_rules": {
            "target_rank_offsets": [0, 1],
            "max_candidates_per_seniority_rank": max_candidates_per_level,
            "category_labels": sorted(
                {
                    category
                    for value in jobs["job_categories"]
                    for category in json.loads(value)
                }
            ),
            "ranking_weights": BROWSING_SCORE_WEIGHTS,
        },
        "edge_count": len(edges),
    }
    representations_path.parent.mkdir(parents=True, exist_ok=True)
    edges_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    representations.to_parquet(representations_path, index=False, compression="zstd")
    edges.to_parquet(edges_path, index=False, compression="zstd")
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return representations, edges


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Gemini job representations and nearby browsing suggestions."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/jobs_clean.csv"),
    )
    parser.add_argument(
        "--prepared-input",
        type=Path,
        default=Path("data/processed/description_full/prepared_jobs.csv"),
        help="Selected description CSV produced by src.job_descriptions.",
    )
    parser.add_argument(
        "--representations-output",
        type=Path,
        default=Path("data/processed/job_representations.parquet"),
    )
    parser.add_argument(
        "--edges-output",
        type=Path,
        default=Path("data/processed/job_move_edges.parquet"),
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        default=Path("data/processed/job_graph_metadata.json"),
        help="JSON output recording the model and suggestion rules.",
    )
    parser.add_argument(
        "--max-candidates-per-level",
        type=int,
        default=DEFAULT_MAX_CANDIDATES_PER_LEVEL,
        help="Maximum outgoing proposals at each allowed target seniority level.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    representations, edges = build_job_graph(
        input_path=args.input,
        representations_path=args.representations_output,
        edges_path=args.edges_output,
        metadata_path=args.metadata_output,
        prepared_path=args.prepared_input,
        max_candidates_per_level=args.max_candidates_per_level,
    )
    sources_with_edges = edges["source_job_id"].nunique()
    print(f"Built {len(representations)} job representations with {MODEL_NAME}.")
    print(
        f"Built {len(edges)} nearby browsing suggestions from {sources_with_edges} "
        f"source jobs."
    )


if __name__ == "__main__":
    main()
