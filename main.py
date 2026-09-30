from pathlib import Path
from src.preprocessing import clean_jobs


if __name__ == "__main__":
    input_path = Path("data/Jobs_NYC_Postings_20260608.csv")

    # Two versions: with salary for the student-facing app, and without salary
    # for modeling runs where pay shouldn't influence how jobs are related.
    clean_jobs(
        input_path=input_path,
        output_path=Path("data/processed/jobs_clean_with_salary.csv"),
        include_salary=True,
    )
    clean_jobs(
        input_path=input_path,
        output_path=Path("data/processed/jobs_clean_no_salary.csv"),
        include_salary=False,
    )
