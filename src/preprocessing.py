"""Cleaning pipeline for job dataset."""

from pathlib import Path
import pandas as pd


SENIORITY_MAP = {
    "Student": 0,
    "Entry-Level": 1,
    "Experienced (non-manager)": 2,
    "Manager": 3,
    "Executive": 4,
}

MODELING_COLUMNS = [
    "Job ID",
    "Business Title",
    "normalized_title",
    "Civil Service Title",
    "Job Category",
    "Career Level",
    "seniority_rank",
    "posting_types",
]

def load_jobs(input_path: Path) -> pd.DataFrame:
    """
    Load job data from a CSV file.

    Args:
        input_path (Path): The path to the input CSV file.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"The file {input_path} does not exist.")
    jobs = pd.read_csv(input_path, low_memory=False)
    jobs.columns = jobs.columns.str.strip()  # Strip whitespace from column names
    return jobs

def remove_exact_duplicates(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Remove exact duplicate rows from the DataFrame.

    Args:
        jobs (pd.DataFrame): The job DataFrame.
    """
    return jobs.drop_duplicates()

def combine_job_postings(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Create one record per Job ID and preserve posting types.

    Args:
        jobs (pd.DataFrame): The job DataFrame.
    """
    jobs = jobs.copy()
    jobs["Posting Type"] = (
        jobs["Posting Type"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    grouped = jobs.groupby("Job ID", as_index=False).agg(
        {
            "Business Title": "first",
            "Civil Service Title": "first",
            "Job Category": "first",
            "Career Level": "first",
            "Job Description": "first",
            "Minimum Qual Requirements": "first",
            "Preferred Skills": "first",
            "Posting Type": lambda values: ", ".join(
                sorted(set(values))
            ),
            "Agency": "first",
        }
    )
    grouped = grouped.rename(columns={"Posting Type": "posting_types"})
    return grouped

def normalize_titles(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize job titles by stripping whitespace and converting to title case.

    Args:
        jobs (pd.DataFrame): The job DataFrame.
    """
    jobs = jobs.copy()
    jobs["normalized_title"] = (
        jobs["Business Title"].fillna("")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.lower()
    )
    return jobs

def add_seniority_rank(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Add a seniority level column based on the Career Level.

    Args:
        jobs (pd.DataFrame): The job DataFrame.
    """
    jobs = jobs.copy()
    jobs["seniority_rank"] = jobs["Career Level"].map(SENIORITY_MAP)
    return jobs

def select_modeling_columns(jobs):
    """Keep only the 8 columns used for modeling."""
    return jobs[[
        "Job ID",
        "Business Title",
        "normalized_title",
        "Civil Service Title",
        "Job Category",
        "Career Level",
        "seniority_rank",
        "posting_types",
    ]].copy()

def validate_jobs(jobs: pd.DataFrame) -> pd.DataFrame:
    """Check the processed dataset before saving it."""
    assert len(jobs) == 1228, f"Expected 1228 rows, got {len(jobs)}"
    assert jobs["normalized_title"].notna().all()
    assert (jobs["normalized_title"] != "").all()
    assert jobs["seniority_rank"].isin([0,1,2,3,4]).all()
    return jobs

def clean_jobs(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    """Run the complete preprocessing pipeline."""
    jobs = load_jobs(input_path)
    jobs = remove_exact_duplicates(jobs)
    jobs = combine_job_postings(jobs)
    jobs = normalize_titles(jobs)
    jobs = add_seniority_rank(jobs)
    jobs = select_modeling_columns(jobs)
    jobs = validate_jobs(jobs)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    jobs.to_csv(output_path, index=False)
    return jobs