"""Build web/public/data/jobs.json from the career-path model artifacts.

Coordinates are a 3D UMAP of the Gemini job embeddings in
data/processed/job_representations.parquet. `next` and `prev` hold the
strongest browsing moves from data/processed/job_move_edges.parquet (one
seniority rank up / down). Requirement fields (education, years, license)
are carried over from the existing jobs.json by job ID.

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

jobs = pd.read_parquet(ROOT / "data/processed/job_representations.parquet")
edges = pd.read_parquet(ROOT / "data/processed/job_move_edges.parquet")
previous = {job["id"]: job for job in json.loads(OUTPUT.read_text())["jobs"]}

coordinates = umap.UMAP(n_components=3, metric="cosine", random_state=42).fit_transform(np.stack(jobs["embedding"]))
coordinates = (coordinates - coordinates.mean(axis=0)) / np.abs(coordinates - coordinates.mean(axis=0)).max() * SCALE

up = edges[edges["move_type"] == "up_one_seniority_rank"].sort_values("ranking_score", ascending=False)
next_ids = up.groupby("source_job_id")["target_job_id"].apply(lambda ids: list(ids[:LINKS_PER_JOB]))
prev_ids = up.groupby("target_job_id")["source_job_id"].apply(lambda ids: list(ids[:LINKS_PER_JOB]))


def number(value):
    return None if pd.isna(value) else round(float(value))


records = []
for (_, job), (x, y, z) in zip(jobs.iterrows(), coordinates):
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
