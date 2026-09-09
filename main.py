from pathlib import Path
from src.preprocessing import clean_jobs


if __name__ == "__main__":
    clean_jobs(
        input_path=Path("data/Jobs_NYC_Postings_20260608.csv"),
        output_path=Path("data/processed/jobs_clean.csv"),
    )
