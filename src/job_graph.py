"""Build job representations and nearby job suggestions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv


MODEL_NAME = "gemini-embedding-2"
MODEL_MAX_INPUT_TOKENS = 8192
EMBEDDING_DIMENSIONS = 1536
DEFAULT_MAX_CANDIDATES_PER_LEVEL = 32

REQUIRED_COLUMNS = (
    "Job ID",
    "Business Title",
    "normalized_title",
    "Civil Service Title",
    "Job Category",
    "job_categories",
    "Career Level",
    "seniority_rank",
    "posting_types",
    "Agency",
    "Job Description",
    "Minimum Qual Requirements",
    "Preferred Skills",
)

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
    *(
        f"{side}_{field}"
        for field in DISPLAY_FIELDS
        for side in ("source", "target")
    ),
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
    """Return a stripped source value without turning missing values into text."""
    if pd.isna(value):
        return ""
    return str(value).strip()


def load_jobs(input_path: Path) -> pd.DataFrame:
    """Load one unique, non-blank identifier per cleaned job posting."""
    jobs = pd.read_csv(input_path, dtype={"Job ID": "string"})
    missing_columns = sorted(set(REQUIRED_COLUMNS).difference(jobs.columns))
    if missing_columns:
        raise ValueError(f"Missing required cleaned-job columns: {missing_columns}")

    jobs["Job ID"] = jobs["Job ID"].fillna("").str.strip()
    if jobs["Job ID"].eq("").any() or jobs["Job ID"].duplicated().any():
        raise ValueError("Expected one non-blank, unique Job ID per job")
    return jobs


def build_role_text(job: pd.Series) -> str:
    """Build the role-only text used for semantic similarity.

    Qualifications and preferred skills stay in the representation artifact, but
    are intentionally excluded here: a posting's requirements do not establish
    a current job holder's qualifications.
    """
    description = job.get("selected_description", job["Job Description"])
    return "\n".join(
        (
            f"Business title: {value_as_text(job['Business Title'])}",
            f"Civil service title: {value_as_text(job['Civil Service Title'])}",
            f"Job category: {value_as_text(job['Job Category'])}",
            f"Job description: {value_as_text(description)}",
        )
    )


def load_prepared_descriptions(jobs: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Use selected descriptions only for matching source jobs."""
    prepared = pd.read_csv(path, dtype={"Job ID": "string"}, low_memory=False)
    selected = prepared.set_index("Job ID")
    jobs = jobs.copy()
    descriptions = []
    statuses = []
    for _, job in jobs.iterrows():
        job_id = str(job["Job ID"])
        if job_id in selected.index:
            if selected.at[job_id, "Job Description"] != job["Job Description"]:
                raise ValueError(
                    f"Prepared description is stale for Job ID {job_id}; "
                    "run src.job_descriptions first"
                )
            descriptions.append(selected.at[job_id, "selected_description"])
            statuses.append(selected.at[job_id, "representation_status"])
        else:
            descriptions.append(job["Job Description"])
            statuses.append("original_fallback")
    jobs["selected_description"] = descriptions
    jobs["representation_status"] = statuses
    return jobs


def embed_roles(
    client, jobs: pd.DataFrame, role_texts: list[str], cached: dict
) -> tuple[np.ndarray, list[int | None]]:
    """Embed full role texts with Gemini; keep qualifications out of role similarity."""
    from google.genai import types

    vectors = []
    new_embeddings = 0
    token_counts: list[int | None] = []
    for index, (job_id, text) in enumerate(zip(jobs["Job ID"], role_texts), start=1):
        saved = cached.get((str(job_id), text))
        token_count = saved[1] if saved is not None else None
        if saved is None and len(text.encode("utf-8")) > MODEL_MAX_INPUT_TOKENS - 2:
            token_count = client.models.count_tokens(model=MODEL_NAME, contents=text).total_tokens
            if token_count > MODEL_MAX_INPUT_TOKENS:
                raise ValueError(
                    f"Job ID {job_id} has {token_count} tokens; "
                    f"{MODEL_NAME} accepts at most {MODEL_MAX_INPUT_TOKENS}"
                )
        if saved is None:
            # Gemini Embedding 2 can treat a plain list as one document.
            response = client.models.embed_content(
                model=MODEL_NAME,
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
            )
            embedding = response.embeddings[0]
            if embedding.statistics and embedding.statistics.truncated:
                raise ValueError(f"Gemini truncated Job ID {job_id}")
            vector = embedding.values
            new_embeddings += 1
        else:
            vector = saved[0]
        token_counts.append(token_count)
        vectors.append(vector)
        if index % 100 == 0 or index == len(role_texts):
            print(f"Prepared {index}/{len(role_texts)} jobs", flush=True)
    print(f"Reused {len(role_texts) - new_embeddings} embeddings; created {new_embeddings}.")
    embeddings = np.asarray(vectors, dtype=np.float32)
    return embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True), token_counts


def title_terms(title: str) -> set[str]:
    """Return non-filler title words for interpretable overlap evidence."""
    return {
        term
        for term in re.findall(r"[a-z0-9]+", title.lower())
        if term not in TITLE_STOP_WORDS
    }


def stable_edge_id(source_job_id: str, target_job_id: str) -> str:
    """Create an identifier that depends only on the two directed endpoints."""
    endpoints = f"{source_job_id}\x1f{target_job_id}".encode()
    return f"move_{hashlib.sha256(endpoints).hexdigest()}"


def normalized_value(value: object) -> str:
    """Normalize source text only for equality comparisons."""
    return " ".join(value_as_text(value).lower().split())


def build_edges(
    jobs: pd.DataFrame,
    embeddings: np.ndarray,
    *,
    max_candidates_per_level: int,
) -> pd.DataFrame:
    """Rank lateral and upward candidates separately without a similarity cutoff."""
    similarities = embeddings @ embeddings.T
    job_ids = jobs["Job ID"].astype(str).tolist()
    ranks = jobs["seniority_rank"].astype(int).to_numpy()
    categories = [
        set(json.loads(value)) for value in jobs["job_categories"]
    ]
    civil_service_titles = [
        normalized_value(value) for value in jobs["Civil Service Title"]
    ]
    title_term_sets = [
        title_terms(value_as_text(value)) for value in jobs["normalized_title"]
    ]
    display = {
        column: [value_as_text(value) for value in jobs[column]]
        for column in DISPLAY_FIELDS.values()
    }

    edge_rows: list[dict[str, object]] = []
    for source_index, source_job_id in enumerate(job_ids):
        eligible_indices = np.flatnonzero(
            ((ranks == ranks[source_index]) | (ranks == ranks[source_index] + 1))
            & (np.arange(len(jobs)) != source_index)
        )
        candidates_by_rank: dict[int, list[dict[str, object]]] = {
            ranks[source_index]: [],
            ranks[source_index] + 1: [],
        }
        for target_index in eligible_indices:
            role_similarity = float(similarities[source_index, target_index])
            shared_terms = sorted(
                title_term_sets[source_index].intersection(title_term_sets[target_index])
            )
            shared_categories = sorted(
                categories[source_index].intersection(categories[target_index])
            )
            same_category = bool(shared_categories)
            same_civil_service_title = (
                civil_service_titles[source_index]
                == civil_service_titles[target_index]
            )
            title_overlap = len(shared_terms) / len(
                title_term_sets[source_index].union(title_term_sets[target_index])
            )
            ranking_score = (
                0.90 * role_similarity
                + 0.06 * title_overlap
                + 0.03 * float(same_civil_service_title)
                + 0.01 * float(same_category)
            )
            candidates_by_rank[ranks[target_index]].append(
                {
                    "target_index": target_index,
                    "role_similarity": role_similarity,
                    "title_term_overlap": title_overlap,
                    "same_job_category": same_category,
                    "shared_job_categories": json.dumps(
                        shared_categories, ensure_ascii=False
                    ),
                    "same_civil_service_title": same_civil_service_title,
                    "shared_title_terms": ", ".join(shared_terms),
                    "ranking_score": ranking_score,
                }
            )

        for candidates in candidates_by_rank.values():
            candidates.sort(
                key=lambda candidate: (
                    -candidate["ranking_score"],
                    job_ids[candidate["target_index"]],
                )
            )
            for candidate in candidates[:max_candidates_per_level]:
                target_index = candidate.pop("target_index")
                target_job_id = job_ids[target_index]
                edge_rows.append(
                    {
                        **candidate,
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
                        **{
                            f"{side}_{field}": display[column][index]
                            for side, index in (
                                ("source", source_index),
                                ("target", target_index),
                            )
                            for field, column in DISPLAY_FIELDS.items()
                        },
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
    """Create job representations and nearby suggestions from the cleaned snapshot."""
    if max_candidates_per_level < 1:
        raise ValueError("max_candidates_per_level must be at least 1")

    jobs = load_prepared_descriptions(load_jobs(input_path), prepared_path)
    role_texts = [build_role_text(job) for _, job in jobs.iterrows()]
    cached = {}
    if representations_path.exists():
        previous = pd.read_parquet(representations_path)
        for row in previous.itertuples(index=False):
            if row.embedding_model == MODEL_NAME and len(row.embedding) == EMBEDDING_DIMENSIONS:
                token_count = (
                    int(row.semantic_text_token_count)
                    if hasattr(row, "semantic_text_token_count") and pd.notna(row.semantic_text_token_count)
                    else None
                )
                cached[(row.job_id, row.semantic_role_text)] = (row.embedding, token_count)
    if all((str(job_id), text) in cached for job_id, text in zip(jobs["Job ID"], role_texts)):
        embeddings, token_counts = embed_roles(None, jobs, role_texts, cached)
    else:
        from google import genai

        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Set GEMINI_API_KEY in .env or your environment")
        with genai.Client(api_key=api_key) as client:
            embeddings, token_counts = embed_roles(client, jobs, role_texts, cached)

    representations = jobs.copy()
    representations.insert(0, "job_id", jobs["Job ID"].astype(str))
    representations["semantic_role_text"] = role_texts
    representations["semantic_text_token_count"] = token_counts
    representations["embedding_model"] = MODEL_NAME
    representations["embedding"] = list(embeddings)

    edges = build_edges(
        jobs,
        embeddings,
        max_candidates_per_level=max_candidates_per_level,
    )
    input_digest = hashlib.sha256(input_path.read_bytes()).hexdigest()
    metadata = {
        "schema_version": 5,
        "input_csv": str(input_path),
        "input_sha256": input_digest,
        "job_count": len(jobs),
        "embedding_model": MODEL_NAME,
        "description_selection": {
            "source": str(prepared_path),
            "extracted": int(jobs["representation_status"].eq("extracted").sum()),
            "original_fallback": int(jobs["representation_status"].eq("original_fallback").sum()),
        },
        "semantic_source_columns": [
            "Business Title",
            "Civil Service Title",
            "Job Category",
            "Job Description",
        ],
        "excluded_from_semantic_similarity": [
            "Minimum Qual Requirements",
            "Preferred Skills",
        ],
        "representation": {
            "strategy": "full role text, one embedding per job",
            "model_token_limit": MODEL_MAX_INPUT_TOKENS,
            "embedding_dimensions": EMBEDDING_DIMENSIONS,
            "long_texts_counted": sum(count is not None for count in token_counts),
            "maximum_counted_tokens": max(
                (count for count in token_counts if count is not None), default=None
            ),
        },
        "edge_rules": {
            "allowed_target_seniority_ranks": "source rank or source rank + 1",
            "max_candidates_per_seniority_rank": max_candidates_per_level,
            "similarity_cutoff": None,
            "category_overlap_uses": "job_categories canonical labels",
            "category_labels": sorted(
                {
                    category
                    for value in jobs["job_categories"]
                    for category in json.loads(value)
                }
            ),
            "scope": "nearby browsing suggestions only; not a route-search boundary",
            "ranking_score": (
                "0.90 * role_similarity + 0.06 * title_term_overlap + "
                "0.03 * same_civil_service_title + 0.01 * same_job_category"
            ),
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
    """Parse command-line paths and browse-suggestion bounds."""
    parser = argparse.ArgumentParser(
        description="Build Gemini job representations and nearby browsing suggestions."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/jobs_clean.csv"),
        help="Cleaned job CSV input.",
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
        help="Parquet output containing source fields, semantic text, and embeddings.",
    )
    parser.add_argument(
        "--edges-output",
        type=Path,
        default=Path("data/processed/job_move_edges.parquet"),
        help="Parquet output containing directed proposed moves and source-grounded evidence.",
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
    """Run the job representation and browsing suggestion pipeline."""
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
    print("Qualifications and preferred skills were not embedded.")
    print(
        f"Built {len(edges)} nearby browsing suggestions from {sources_with_edges} "
        f"source jobs (at most {args.max_candidates_per_level} per target level); "
        "not a limit on future route search."
    )


if __name__ == "__main__":
    main()
