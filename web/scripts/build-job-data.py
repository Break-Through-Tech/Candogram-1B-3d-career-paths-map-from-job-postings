"""Build web/public/data/jobs.json from the career-path model artifacts.

Seniority level is the map's vertical axis: each of the five levels is its own
layer, LEVEL_GAP apart, and a job's height within its layer follows its salary
percentile among jobs of that level (LAYER_THICKNESS), so layers never overlap.
The horizontal position (x, z) is a 2D UMAP of the Gemini job embeddings in
data/processed/job_representations.parquet after projecting out the span of the
level centroids, so it places jobs by field only and a job sits near its
same-field neighbours at the other levels. Salary stays out of the horizontal
layout because it is a proxy for level. `next` and `prev` hold the strongest
browsing moves from data/processed/job_move_edges.parquet (one seniority rank
up / down). Requirement fields (education, years, license) are carried over
from the existing jobs.json by job ID.

Usage: python web/scripts/build-job-data.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import umap

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "web/public/data/jobs.json"
LINKS_PER_JOB = 3
SCALE = 10
LEVEL_GAP = 4
LAYER_THICKNESS = 1.2
MIDDLE_RANK = 2

jobs = pd.read_parquet(ROOT / "data/processed/job_representations.parquet")
edges = pd.read_parquet(ROOT / "data/processed/job_move_edges.parquet")
previous = {job["id"]: job for job in json.loads(OUTPUT.read_text())["jobs"]}

embeddings = np.stack(jobs["embedding"]).astype(np.float64)
ranks = jobs["seniority_rank"].to_numpy()
level_centroids = np.stack([embeddings[ranks == rank].mean(axis=0) for rank in range(5)])
level_axes = np.linalg.svd(level_centroids - level_centroids.mean(axis=0), full_matrices=False)[2][:4]
field_embeddings = embeddings - (embeddings @ level_axes.T) @ level_axes
plane = umap.UMAP(n_components=2, random_state=42).fit_transform(field_embeddings)
plane = (plane - plane.mean(axis=0)) / np.abs(plane - plane.mean(axis=0)).max() * SCALE

salary_mid = jobs[["annual_salary_from", "annual_salary_to"]].mean(axis=1)
salary_percentile = salary_mid.groupby(jobs["seniority_rank"]).rank(pct=True).fillna(0.5)
heights = (ranks - MIDDLE_RANK) * LEVEL_GAP + (salary_percentile.to_numpy() - 0.5) * LAYER_THICKNESS

up = edges[edges["move_type"] == "up_one_seniority_rank"].sort_values("ranking_score", ascending=False)
next_ids = up.groupby("source_job_id")["target_job_id"].apply(lambda ids: list(ids[:LINKS_PER_JOB]))
prev_ids = up.groupby("target_job_id")["source_job_id"].apply(lambda ids: list(ids[:LINKS_PER_JOB]))


def number(value):
    return None if pd.isna(value) else round(float(value))


records = []
for (_, job), (x, z), y in zip(jobs.iterrows(), plane, heights):
    job_id = job["Job ID"]
    salary_from, salary_to = number(job["annual_salary_from"]), number(job["annual_salary_to"])
    salaries = [s for s in (salary_from, salary_to) if s is not None]
    requirements = previous.get(job_id, {})
    records.append(
        {
            "id": job_id,
            "title": " ".join(job["Business Title"].split()),
            "agency": job["Agency"],
            "categories": json.loads(job["job_categories"]),
            "career_level": job["Career Level"],
            "seniority_rank": int(job["seniority_rank"]),
            "salary_from": salary_from,
            "salary_to": salary_to,
            "salary_mid": round(sum(salaries) / len(salaries)) if salaries else None,
            "min_education_rank": requirements.get("min_education_rank"),
            "min_years_experience": requirements.get("min_years_experience"),
            "license": requirements.get("license", False),
            "x": round(float(x), 3),
            "y": round(float(y), 3),
            "z": round(float(z), 3),
            "next": next_ids.get(job_id, []),
            "prev": prev_ids.get(job_id, []),
        }
    )

OUTPUT.write_text(json.dumps({"placeholder": False, "jobs": records}, separators=(",", ":")))
print(f"Wrote {len(records)} jobs to {OUTPUT}")
