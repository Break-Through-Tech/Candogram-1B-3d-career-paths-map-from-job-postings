"""Cleaning pipeline for job dataset."""

import json
from pathlib import Path
import re
import pandas as pd


CATEGORY_LABELS = (
    "Engineering, Architecture, & Planning",
    "Health",
    "Legal Affairs",
    "Constituent Services & Community Programs",
    "Finance, Accounting, & Procurement",
    "Administration & Human Resources",
    "Technology, Data & Innovation",
    "Building Operations & Maintenance",
    "Social Services",
    "Public Safety, Inspections, & Enforcement",
    "Policy, Research & Analysis",
    "Communications & Intergovernmental Affairs",
    "Mental Health",
    "Green Jobs",
)

CATEGORY_PATTERNS = [
    (
        category,
        re.compile(
            r"(?<!\w)" + r"\s+".join(map(re.escape, category.split())) + r"(?!\w)",
            re.IGNORECASE,
        ),
    )
    for category in sorted(CATEGORY_LABELS, key=len, reverse=True)
]

SENIORITY_MAP = {
    "Student": 0,
    "Entry-Level": 1,
    "Experienced (non-manager)": 2,
    "Manager": 3,
    "Executive": 4,
}

ANNUALIZATION_MULTIPLIERS = {
    "Annual": 1,
    "Hourly": 2080,
    "Daily": 260,
}

MODELING_COLUMNS = [
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
    "Salary Range From",
    "Salary Range To",
    "Salary Frequency",
    "normalized_salary_frequency",
    "annual_salary_from",
    "annual_salary_to",
    "salary_annualization_basis",
]

JOB_FIELDS = [
    "Business Title",
    "Civil Service Title",
    "Job Category",
    "Career Level",
    "Job Description",
    "Minimum Qual Requirements",
    "Preferred Skills",
    "Agency",
    "Salary Range From",
    "Salary Range To",
    "Salary Frequency",
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

    if jobs["Job ID"].isna().any():
        raise ValueError("Job ID is missing from one or more postings")
    for column in JOB_FIELDS:
        values = jobs[column].fillna("").astype(str).str.strip()
        conflicting = jobs.assign(_value=values).groupby("Job ID")["_value"].nunique()
        if (conflicting > 1).any():
            job_id = conflicting[conflicting > 1].index[0]
            raise ValueError(f"Conflicting {column} for Job ID {job_id}")

    grouped = jobs.groupby("Job ID", as_index=False).agg(
        {
            **{column: "first" for column in JOB_FIELDS},
            "Posting Type": lambda values: ", ".join(
                sorted(set(values))
            ),
        }
    )
    grouped = grouped.rename(columns={"Posting Type": "posting_types"})
    return grouped

def normalize_titles(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize job titles by collapsing whitespace and converting to lowercase.

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

def normalize_job_categories(jobs: pd.DataFrame) -> pd.DataFrame:
    """Map combined source category text to a JSON list of canonical labels."""
    jobs = jobs.copy()

    def extract_categories(value: object) -> str:
        text = " ".join(str(value).split())
        matched = set()
        spans = []
        for category, pattern in CATEGORY_PATTERNS:
            for match in pattern.finditer(text):
                if not any(
                    match.start() < end and match.end() > start
                    for start, end in spans
                ):
                    matched.add(category)
                    spans.append(match.span())
        if not matched:
            raise ValueError(f"Unmapped Job Category: {value}")
        return json.dumps(
            [category for category in CATEGORY_LABELS if category in matched],
            ensure_ascii=False,
        )

    jobs["job_categories"] = jobs["Job Category"].map(extract_categories)
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

def add_annualized_salary(jobs: pd.DataFrame) -> pd.DataFrame:
    """Add estimated full-time annual salary ranges and retain source values."""
    jobs = jobs.copy()
    jobs["normalized_salary_frequency"] = jobs["Salary Frequency"]

    explicitly_hourly = (
        jobs["Job Description"]
        .fillna("")
        .str.contains(r"\bhourly\b|\bper\s*/?\s*hour\b", case=False, regex=True)
    )
    signature_columns = [
        "Business Title",
        "Civil Service Title",
        "Salary Range From",
        "Salary Range To",
    ]
    hourly_signatures = set(
        map(
            tuple,
            jobs.loc[
                explicitly_hourly & jobs["Salary Frequency"].eq("Daily"),
                signature_columns,
            ].to_numpy(),
        )
    )
    daily_hourly_signature = (
        jobs["Salary Frequency"].eq("Daily")
        & jobs[signature_columns].apply(tuple, axis=1).isin(hourly_signatures)
    )
    jobs.loc[daily_hourly_signature, "normalized_salary_frequency"] = "Hourly"
    jobs["salary_annualization_basis"] = jobs["normalized_salary_frequency"]
    jobs.loc[daily_hourly_signature, "salary_annualization_basis"] = (
        "Hourly rate stated in matching job description"
    )
    multipliers = jobs["normalized_salary_frequency"].map(
        ANNUALIZATION_MULTIPLIERS
    )
    jobs["annual_salary_from"] = jobs["Salary Range From"] * multipliers
    jobs["annual_salary_to"] = jobs["Salary Range To"] * multipliers
    jobs.loc[jobs["Salary Range From"].eq(0), "annual_salary_from"] = pd.NA
    return jobs

def select_modeling_columns(jobs):
    """Keep text features and provenance alongside title-only baseline fields."""
    return jobs[MODELING_COLUMNS].copy()

def validate_jobs(jobs: pd.DataFrame) -> pd.DataFrame:
    """Check the processed dataset before saving it."""
    if jobs.empty or jobs["Job ID"].isna().any() or jobs["Job ID"].duplicated().any():
        raise ValueError("Expected one non-null, unique Job ID per job")
    if jobs["normalized_title"].eq("").any() or jobs["normalized_title"].isna().any():
        raise ValueError("Each job needs a non-blank Business Title")
    if jobs["seniority_rank"].isna().any():
        raise ValueError("Unknown or missing Career Level")
    if jobs["Job Description"].fillna("").astype(str).str.strip().eq("").any():
        raise ValueError("Each job needs a non-blank Job Description")
    return jobs

def clean_jobs(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    """Run the complete preprocessing pipeline."""
    jobs = load_jobs(input_path)
    jobs = remove_exact_duplicates(jobs)
    jobs = combine_job_postings(jobs)
    jobs = normalize_titles(jobs)
    jobs = normalize_job_categories(jobs)
    jobs = add_seniority_rank(jobs)
    jobs = add_annualized_salary(jobs)
    jobs = select_modeling_columns(jobs)
    jobs = validate_jobs(jobs)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    jobs.to_csv(output_path, index=False)
    return jobs