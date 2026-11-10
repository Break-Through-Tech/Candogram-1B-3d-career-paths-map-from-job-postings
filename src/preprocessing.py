import json
import re
from pathlib import Path

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


def load_jobs(input_path: str | Path) -> pd.DataFrame:
    jobs = pd.read_csv(input_path, low_memory=False)
    jobs.columns = jobs.columns.str.strip()
    return jobs


def combine_job_postings(jobs: pd.DataFrame) -> pd.DataFrame:
    jobs["Posting Type"] = jobs["Posting Type"].fillna("Unknown").str.strip()

    if jobs["Job ID"].isna().any():
        raise ValueError("Job ID is missing from one or more postings")
    normalized = (
        jobs[JOB_FIELDS].fillna("").astype(str).apply(lambda column: column.str.strip())
    )
    conflicts = normalized.groupby(jobs["Job ID"]).nunique()
    for column in JOB_FIELDS:
        if conflicts[column].gt(1).any():
            job_id = conflicts.index[conflicts[column].gt(1)][0]
            raise ValueError(f"Conflicting {column} for Job ID {job_id}")

    grouped = jobs.groupby("Job ID", as_index=False).agg(
        {
            **{column: "first" for column in JOB_FIELDS},
            "Posting Type": lambda values: ", ".join(sorted(set(values))),
        }
    )
    return grouped.rename(columns={"Posting Type": "posting_types"})


def normalize_titles(jobs: pd.DataFrame) -> pd.DataFrame:
    jobs["normalized_title"] = (
        jobs["Business Title"]
        .fillna("")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.lower()
    )
    return jobs


def normalize_job_categories(jobs: pd.DataFrame) -> pd.DataFrame:
    """Map combined source category text to a JSON list of canonical labels."""

    def extract_categories(value: object) -> str:
        text = " ".join(str(value).split())
        matched = set()
        spans = []
        for category, pattern in CATEGORY_PATTERNS:
            for match in pattern.finditer(text):
                if not any(
                    match.start() < end and match.end() > start for start, end in spans
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


def add_annualized_salary(jobs: pd.DataFrame) -> pd.DataFrame:
    jobs["normalized_salary_frequency"] = jobs["Salary Frequency"]

    # Daily postings with the same titles and salary bounds share one pay rate, but
    # only some descriptions say it is hourly, so reclassify every match.
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
    daily_hourly_signature = jobs["Salary Frequency"].eq("Daily") & jobs[
        signature_columns
    ].apply(tuple, axis=1).isin(hourly_signatures)
    jobs.loc[daily_hourly_signature, "normalized_salary_frequency"] = "Hourly"
    jobs["salary_annualization_basis"] = jobs["normalized_salary_frequency"]
    jobs.loc[daily_hourly_signature, "salary_annualization_basis"] = (
        "Hourly rate stated in matching job description"
    )
    multipliers = jobs["normalized_salary_frequency"].map(ANNUALIZATION_MULTIPLIERS)
    jobs["annual_salary_from"] = jobs["Salary Range From"] * multipliers
    jobs["annual_salary_to"] = jobs["Salary Range To"] * multipliers
    jobs.loc[jobs["Salary Range From"].eq(0), "annual_salary_from"] = pd.NA
    return jobs


def validate_jobs(jobs: pd.DataFrame) -> pd.DataFrame:
    if jobs.empty:
        raise ValueError("Expected at least one job")
    if jobs["normalized_title"].eq("").any():
        raise ValueError("Each job needs a non-blank Business Title")
    if jobs["seniority_rank"].isna().any():
        raise ValueError("Unknown or missing Career Level")
    if jobs["Job Description"].fillna("").astype(str).str.strip().eq("").any():
        raise ValueError("Each job needs a non-blank Job Description")
    return jobs


def clean_jobs(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    jobs = load_jobs(input_path).drop_duplicates()
    jobs = combine_job_postings(jobs)
    jobs = normalize_titles(jobs)
    jobs = normalize_job_categories(jobs)
    jobs["seniority_rank"] = jobs["Career Level"].map(SENIORITY_MAP)
    jobs = add_annualized_salary(jobs)
    jobs = jobs[MODELING_COLUMNS]
    jobs = validate_jobs(jobs)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    jobs.to_csv(output_path, index=False)
    return jobs
