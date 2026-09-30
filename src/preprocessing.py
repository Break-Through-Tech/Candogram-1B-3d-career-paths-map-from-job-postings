"""Cleaning pipeline for job dataset."""

import re
from pathlib import Path

import numpy as np
import pandas as pd


SENIORITY_MAP = {
    "Student": 0,
    "Entry-Level": 1,
    "Experienced (non-manager)": 2,
    "Manager": 3,
    "Executive": 4,
}

# Full-time-equivalent conversions used to put all salaries on a yearly scale.
HOURS_PER_YEAR = 2080  # 40 hrs/week x 52 weeks
DAYS_PER_YEAR = 260  # 5 days/week x 52 weeks

# `# Of Positions` values at or above this are data-entry errors (e.g. 9999);
# real recruitment drives in this data top out around 250.
POSITIONS_OUTLIER_THRESHOLD = 500

EDUCATION_LEVELS = [
    "None",
    "High school",
    "Associate",
    "Bachelor's",
    "Master's",
    "Doctorate/Professional",
]

# Checked from highest to lowest; the first match wins for a requirement route.
EDUCATION_PATTERNS = [
    (5, r"doctora|ph\.?\s?d|juris doctor|law school|medical degree|\bm\.d\.|admitted to (?:practice|the (?:new york state )?bar)"),
    (4, r"master'?s|graduate degree"),
    (3, r"baccalaureate|bachelor"),
    (2, r"associate degree|associate'?s degree|60 semester credits"),
    (1, r"high school|equivalency diploma|\bged\b|matriculat"),
]

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15,
}

# "two years of", "four (4) years of", "3 years full-time", "five years' experience"
YEARS_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?|" + "|".join(NUMBER_WORDS) + r")\s*(?:\(\d+\)\s*)?"
    r"(?:full[- ]time\s+)?years?(?:'|\s+of|\s+full[- ]time|\s+experience)",
    re.IGNORECASE,
)

# Alternative routes in requirements: "1. ...; or 2. ...", "(1) ... or (2) ...",
# or unnumbered "A baccalaureate degree; or An associate degree and ...".
ROUTE_SPLIT_PATTERN = re.compile(r"(?:^|\s)\(?\d\)?[.)]\s+|;\s*or\b", re.IGNORECASE)

LICENSE_PATTERN = re.compile(r"licen[sc]e|certificat|certified|registration as", re.IGNORECASE)

NO_REQUIREMENTS_PATTERN = re.compile(r"no (?:formal )?education or experience requirement", re.IGNORECASE)

SALARY_COLUMNS = [
    "salary_from_annual",
    "salary_to_annual",
    "salary_midpoint_annual",
    "salary_frequency",
    "salary_placeholder_flag",
]

MODELING_COLUMNS = [
    "Job ID",
    "Business Title",
    "normalized_title",
    "Civil Service Title",
    "Agency",
    "Job Category",
    "job_categories",
    "Career Level",
    "seniority_rank",
    "posting_types",
    "min_education_level",
    "min_education_rank",
    "min_years_experience",
    "license_or_cert_mentioned",
    "Minimum Qual Requirements",
    "Preferred Skills",
    "Job Description",
    "number_of_positions",
    "positions_outlier_flag",
    "posting_date",
    "post_until",
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

def parse_dates(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Parse posting dates. `Post Until` uses DD-MON-YYYY; the others use MM/DD/YYYY.

    Args:
        jobs (pd.DataFrame): The job DataFrame.
    """
    jobs = jobs.copy()
    jobs["posting_date"] = pd.to_datetime(jobs["Posting Date"], format="%m/%d/%Y", errors="coerce")
    jobs["post_until"] = pd.to_datetime(jobs["Post Until"], format="%d-%b-%Y", errors="coerce")
    return jobs

def combine_job_postings(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Create one record per Job ID and preserve posting types.

    Internal and external versions of the same job become one row. Text fields
    come from the most recently posted version.

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
    jobs = jobs.sort_values("posting_date", ascending=False, na_position="last")

    first_columns = [
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
        "# Of Positions",
        "posting_date",
        "post_until",
    ]
    grouped = jobs.groupby("Job ID", as_index=False, sort=False).agg(
        {
            **{column: "first" for column in first_columns},
            "Posting Type": lambda values: ", ".join(
                sorted(set(values))
            ),
        }
    )
    grouped = grouped.rename(columns={"Posting Type": "posting_types"})
    return grouped.sort_values("Job ID").reset_index(drop=True)

def normalize_titles(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize job titles by stripping whitespace and converting to lower case.

    Args:
        jobs (pd.DataFrame): The job DataFrame.
    """
    jobs = jobs.copy()
    for column in ["Business Title", "Civil Service Title", "Agency"]:
        jobs[column] = jobs[column].fillna("").str.replace(r"\s+", " ", regex=True).str.strip()
    jobs["normalized_title"] = jobs["Business Title"].str.lower()
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

def annualize_salary(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Convert hourly and daily salaries to yearly amounts so they're comparable.

    Args:
        jobs (pd.DataFrame): The job DataFrame.
    """
    jobs = jobs.copy()
    multiplier = jobs["Salary Frequency"].map(
        {"Annual": 1, "Hourly": HOURS_PER_YEAR, "Daily": DAYS_PER_YEAR}
    )
    salary_from = pd.to_numeric(jobs["Salary Range From"], errors="coerce")
    salary_to = pd.to_numeric(jobs["Salary Range To"], errors="coerce")

    # A $0 minimum is a placeholder, not a real salary.
    jobs["salary_placeholder_flag"] = salary_from.eq(0)
    jobs["salary_from_annual"] = (salary_from * multiplier).where(~jobs["salary_placeholder_flag"]).round(2)
    jobs["salary_to_annual"] = (salary_to * multiplier).round(2)
    jobs["salary_midpoint_annual"] = (
        jobs[["salary_from_annual", "salary_to_annual"]].mean(axis=1).round(2)
    )
    jobs["salary_frequency"] = jobs["Salary Frequency"]
    return jobs

def flag_position_outliers(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Flag implausible `# Of Positions` values instead of dropping them.

    Args:
        jobs (pd.DataFrame): The job DataFrame.
    """
    jobs = jobs.copy()
    jobs["number_of_positions"] = pd.to_numeric(jobs["# Of Positions"], errors="coerce")
    jobs["positions_outlier_flag"] = jobs["number_of_positions"] >= POSITIONS_OUTLIER_THRESHOLD
    return jobs

def _segment(value: str, vocabulary: set[str]) -> list[str] | None:
    """Split `value` on spaces into a sequence of vocabulary entries, if possible."""
    n = len(value)
    pieces_until = [None] * (n + 1)
    pieces_until[0] = []
    for end in range(1, n + 1):
        if end < n and value[end] != " ":
            continue
        for start in range(end):
            if pieces_until[start] is None:
                continue
            piece = value[start:end].strip()
            if piece in vocabulary:
                pieces_until[end] = pieces_until[start] + [piece]
                break
    return pieces_until[n]

def build_category_vocabulary(raw_categories: list[str]) -> tuple[set[str], dict[str, list[str]]]:
    """
    Discover the atomic job categories from the data.

    Many raw values are several categories joined by a single space, e.g.
    "Health Public Safety, Inspections, & Enforcement". Since category names
    contain commas and ampersands themselves, they can't be split on
    punctuation. Instead, the shortest values that can't be built from other
    values are treated as atomic, and longer values are split into them.

    Args:
        raw_categories (list[str]): Unique raw `Job Category` values.
    """
    atomic: set[str] = set()
    splits: dict[str, list[str]] = {}
    for value in sorted(raw_categories, key=len):
        pieces = _segment(value, atomic)
        if pieces is not None and len(pieces) >= 2:
            splits[value] = pieces
        else:
            atomic.add(value)
    return atomic, splits

def split_job_categories(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Add `job_categories`: the atomic categories for each job, joined by "; ".

    Args:
        jobs (pd.DataFrame): The job DataFrame.
    """
    jobs = jobs.copy()
    raw = jobs["Job Category"].fillna("").str.strip()
    _, splits = build_category_vocabulary([value for value in raw.unique() if value])
    jobs["job_categories"] = raw.map(lambda value: "; ".join(splits.get(value, [value])) if value else "")
    return jobs

def _education_rank(text: str) -> int | None:
    lowered = text.lower()
    for rank, pattern in EDUCATION_PATTERNS:
        if re.search(pattern, lowered):
            return rank
    return None

def _years_of_experience(text: str) -> float | None:
    years = []
    for match in YEARS_PATTERN.finditer(text):
        token = match.group(1).lower()
        years.append(float(NUMBER_WORDS.get(token, token)))
    # "three years of ..., one year of which must be supervisory" -> 3
    return max(years) if years else None

def parse_requirements(text: str) -> tuple[int | None, float | None]:
    """
    Estimate the minimum education rank and years of experience for a job.

    NYC postings usually list numbered alternative routes, e.g. "1. A
    baccalaureate degree and two years of experience; or 2. A high school
    diploma and six years of experience". Each route is parsed separately and
    the least demanding value of each is returned. The two values can come from
    different routes.

    Args:
        text (str): The `Minimum Qual Requirements` text.
    """
    if not isinstance(text, str) or not text.strip():
        return None, None
    if NO_REQUIREMENTS_PATTERN.search(text):
        return 0, 0.0

    education = []
    years = []
    for route in ROUTE_SPLIT_PATTERN.split(text):
        route_education = _education_rank(route)
        route_years = _years_of_experience(route)
        if route_education is not None:
            education.append(route_education)
            # A route that only asks for a degree needs no experience.
            years.append(route_years or 0.0)
        elif route_years is not None:
            years.append(route_years)
    return (min(education) if education else None, min(years) if years else None)

def extract_requirements(jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Add minimum education and years of experience parsed from requirements text.

    Args:
        jobs (pd.DataFrame): The job DataFrame.
    """
    jobs = jobs.copy()
    parsed = jobs["Minimum Qual Requirements"].map(parse_requirements)
    jobs["min_education_rank"] = parsed.map(lambda pair: pair[0]).astype("Int64")
    jobs["min_education_level"] = jobs["min_education_rank"].map(dict(enumerate(EDUCATION_LEVELS)))
    jobs["min_years_experience"] = parsed.map(lambda pair: pair[1])
    jobs["license_or_cert_mentioned"] = (
        jobs["Minimum Qual Requirements"].fillna("").str.contains(LICENSE_PATTERN)
    )
    return jobs

def select_modeling_columns(jobs: pd.DataFrame, include_salary: bool = True) -> pd.DataFrame:
    """
    Keep only the columns used for modeling and the web app.

    Args:
        jobs (pd.DataFrame): The job DataFrame.
        include_salary (bool): Whether to keep the salary columns.
    """
    columns = MODELING_COLUMNS + (SALARY_COLUMNS if include_salary else [])
    return jobs[columns].copy()

def validate_jobs(jobs: pd.DataFrame) -> pd.DataFrame:
    """Check the processed dataset before saving it."""
    assert jobs["Job ID"].is_unique, "Expected one row per Job ID"
    assert jobs["normalized_title"].notna().all()
    assert (jobs["normalized_title"] != "").all()
    assert jobs["seniority_rank"].isin([0,1,2,3,4]).all()
    if "salary_from_annual" in jobs:
        # Every non-placeholder salary should be a plausible yearly amount.
        real = jobs.loc[~jobs["salary_placeholder_flag"], "salary_from_annual"]
        assert real.between(10_000, 1_000_000).all(), "Salary annualization produced an implausible value"
    return jobs

def clean_jobs(
    input_path: str | Path,
    output_path: str | Path,
    include_salary: bool = True,
) -> pd.DataFrame:
    """
    Run the complete preprocessing pipeline.

    Args:
        input_path (str | Path): Raw postings CSV.
        output_path (str | Path): Where to write the cleaned CSV.
        include_salary (bool): Keep the annualized salary columns in the output.
    """
    jobs = load_jobs(input_path)
    jobs = remove_exact_duplicates(jobs)
    jobs = parse_dates(jobs)
    jobs = combine_job_postings(jobs)
    jobs = normalize_titles(jobs)
    jobs = add_seniority_rank(jobs)
    jobs = annualize_salary(jobs)
    jobs = flag_position_outliers(jobs)
    jobs = split_job_categories(jobs)
    jobs = extract_requirements(jobs)
    jobs = select_modeling_columns(jobs, include_salary=include_salary)
    jobs = validate_jobs(jobs)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    jobs.to_csv(output_path, index=False)
    return jobs
