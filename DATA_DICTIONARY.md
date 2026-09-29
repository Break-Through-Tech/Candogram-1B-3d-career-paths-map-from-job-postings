# Data Dictionary

Reference documentation for the datasets and generated artifacts in the career paths pipeline.

---

## Datasets Overview

| File | Rows | Columns | Description |
|---|---:|---:|---|
| `data/Jobs_NYC_Postings_20260608.csv` | 2,362 | 30 | Raw NYC Open Data job postings snapshot. |
| `data/processed/jobs_clean.csv` | 1,228 | 12 | Cleaned job dataset produced by `src/preprocessing.py`, aggregated to one row per `Job ID`. |
| `data/processed/job_representations.parquet` | 1,228 | 16 | Job representations with dense vector embeddings produced by `src/job_graph.py`. |
| `data/processed/job_move_edges.parquet` | 77,278 | 20 | Directed edges between job nodes with similarity and scoring metrics. |
| `data/processed/job_graph_metadata.json` | N/A | N/A | Configuration parameters and pipeline execution statistics. |

---

## Raw Job Postings (`data/Jobs_NYC_Postings_20260608.csv`)

| Column | Type | Null Count | Description |
|---|---|---:|---|
| `Job ID` | `int64` | 0 | Unique job posting identifier. |
| `Agency` | `string` | 0 | NYC municipal agency advertising the position. |
| `Posting Type` | `string` | 0 | Hiring channel: `Internal` or `External`. |
| `# Of Positions` | `int64` | 0 | Number of open vacancies for the posting. |
| `Business Title` | `string` | 0 | Public-facing operational title. |
| `Civil Service Title` | `string` | 0 | Official civil service classification title. |
| `Title Classification` | `string` | 0 | Civil service jurisdictional class (e.g., `Competitive-1`, `Non-Competitive-5`, `Exempt-4`). |
| `Title Code No` | `string` | 0 | Five-digit civil service title code. |
| `Level` | `string` | 0 | Assignment level or grade within the civil service title (e.g., `00`, `01`, `02`, `M1`). |
| `Job Category` | `string` | 0 | Occupational domain category. May contain multiple comma-separated categories. |
| `Full-Time/Part-Time indicator` | `string` | 0 | Employment schedule: `F` (Full-Time) or `P` (Part-Time). |
| `Career Level` | `string` | 0 | Seniority classification (`Student`, `Entry-Level`, `Experienced (non-manager)`, `Manager`, `Executive`). |
| `Salary Range From` | `float64` | 0 | Minimum base salary or wage rate. |
| `Salary Range To` | `float64` | 0 | Maximum base salary or wage rate. |
| `Salary Frequency` | `string` | 0 | Pay frequency unit: `Annual`, `Hourly`, or `Daily`. |
| `Work Location` | `string` | 0 | Primary work facility or location description. |
| `Division/Work Unit` | `string` | 0 | Operating division or bureau within the agency. |
| `Job Description` | `string` | 0 | Position overview, primary duties, and responsibilities. |
| `Minimum Qual Requirements` | `string` | 36 | Required education, experience, licenses, and certifications. |
| `Preferred Skills` | `string` | 1,201 | Desired qualifications, technical skills, or domain expertise. |
| `Additional Information` | `string` | 1,752 | Supplemental notes regarding benefits, work conditions, or appointment rules. |
| `To Apply` | `string` | 1,461 | Application submission instructions and portal links. |
| `Hours/Shift` | `string` | 2,048 | Work schedule, shift hours, and weekly time commitments. |
| `Work Location 1` | `string` | 0 | Secondary or standardized work site address. |
| `Recruitment Contact` | `float64` | 2,362 | Dedicated recruitment contact identifier. Unpopulated in this snapshot. |
| `Residency Requirement` | `string` | 0 | NYC administrative code residency regulations governing the title. |
| `Posting Date` | `string` | 0 | Initial publication date (`MM/DD/YYYY`). |
| `Post Until` | `string` | 44 | Application deadline date (`DD-MON-YYYY`). |
| `Posting Updated` | `string` | 0 | Date of last modification to the posting (`MM/DD/YYYY`). |
| `Process Date` | `string` | 0 | Date the record was extracted from the source database (`MM/DD/YYYY`). |

---

## Cleaned Job Postings (`data/processed/jobs_clean.csv`)

Aggregated by `Job ID`. Exact duplicate rows are removed, and multi-posting listings (internal and external) are consolidated into single records.

| Column | Type | Null Count | Source / Derivation | Description |
|---|---|---:|---|---|
| `Job ID` | `int64` | 0 | `Job ID` | Unique job identifier. |
| `Business Title` | `string` | 0 | `Business Title` | Operational business title. |
| `normalized_title` | `string` | 0 | `Business Title` | Lowercased business title with whitespace normalized. |
| `Civil Service Title` | `string` | 0 | `Civil Service Title` | Civil service classification title. |
| `Job Category` | `string` | 0 | `Job Category` | Occupational category text. |
| `Career Level` | `string` | 0 | `Career Level` | Seniority category label. |
| `seniority_rank` | `int64` | 0 | `Career Level` | Ordinal seniority integer rank (0 to 4). |
| `posting_types` | `string` | 0 | `Posting Type` | Comma-separated list of active posting channels (e.g., `External, Internal`). |
| `Agency` | `string` | 0 | `Agency` | Hiring agency name. |
| `Job Description` | `string` | 0 | `Job Description` | Position duties and responsibilities. |
| `Minimum Qual Requirements` | `string` | 20 | `Minimum Qual Requirements` | Minimum qualifications and education requirements. |
| `Preferred Skills` | `string` | 614 | `Preferred Skills` | Preferred skills and experience. |

---

## Seniority Mapping

`seniority_rank` is mapped from `Career Level` in `src/preprocessing.py`:

| Career Level | seniority_rank |
|---|---:|
| `Student` | 0 |
| `Entry-Level` | 1 |
| `Experienced (non-manager)` | 2 |
| `Manager` | 3 |
| `Executive` | 4 |

---

## Job Representations (`data/processed/job_representations.parquet`)

Generated by `src/job_graph.py` from `data/processed/jobs_clean.csv`. Contains cleaned job columns plus semantic representation fields.

| Column | Type | Description |
|---|---|---|
| `job_id` | `string` | String-formatted `Job ID`. |
| `Business Title` | `string` | Operational business title. |
| `normalized_title` | `string` | Lowercased, whitespace-normalized title. |
| `Civil Service Title` | `string` | Official civil service title. |
| `Job Category` | `string` | Occupational category. |
| `Career Level` | `string` | Seniority level string. |
| `seniority_rank` | `int64` | Seniority rank integer (0–4). |
| `posting_types` | `string` | Posting channel types. |
| `Agency` | `string` | Hiring agency name. |
| `Job Description` | `string` | Full job description text. |
| `Minimum Qual Requirements` | `string` | Minimum qualification requirements text. |
| `Preferred Skills` | `string` | Preferred skills text. |
| `semantic_role_text` | `string` | Formatted role text used as embedding input (`Business title`, `Civil service title`, `Job category`, `Job description`). |
| `semantic_text_token_count` | `int64` | Token count returned by Gemini API for texts verified against the input limit; null for texts below verification threshold. |
| `embedding_model` | `string` | Model identifier used for vector generation (`gemini-embedding-2`). |
| `embedding` | `list<float>` | 1,536-dimensional L2-normalized vector embedding. |

---

## Job Move Edges (`data/processed/job_move_edges.parquet`)

Directed graph edges generated by `src/job_graph.py`. Connects source jobs to target jobs at the same seniority rank (`lateral`) or one rank higher (`up_one_seniority_rank`).

| Column | Type | Description |
|---|---|---|
| `edge_id` | `string` | SHA-256 hash derived from source and target job IDs (`move_<hash>`). |
| `source_job_id` | `string` | Origin `Job ID`. |
| `target_job_id` | `string` | Destination `Job ID`. |
| `move_type` | `string` | Seniority transition type: `lateral` or `up_one_seniority_rank`. |
| `source_seniority_rank` | `int64` | Seniority rank of the source job. |
| `target_seniority_rank` | `int64` | Seniority rank of the target job. |
| `role_similarity` | `float64` | Cosine similarity between source and target `embedding` vectors. |
| `title_term_overlap` | `float64` | Jaccard overlap ratio between non-stopword tokens in source and target normalized titles. |
| `same_job_category` | `bool` | Boolean flag indicating whether source and target share identical `Job Category`. |
| `same_civil_service_title` | `bool` | Boolean flag indicating whether source and target share identical `Civil Service Title`. |
| `shared_title_terms` | `string` | Comma-separated list of common non-stopword tokens in normalized titles. |
| `ranking_score` | `float64` | Composite score used to order candidate moves: `0.90 * role_similarity + 0.06 * title_term_overlap + 0.03 * same_civil_service_title + 0.01 * same_job_category`. |
| `source_business_title` | `string` | Business title of the origin job. |
| `target_business_title` | `string` | Business title of the destination job. |
| `source_civil_service_title` | `string` | Civil service title of the origin job. |
| `target_civil_service_title` | `string` | Civil service title of the destination job. |
| `source_job_category` | `string` | Occupational category of the origin job. |
| `target_job_category` | `string` | Occupational category of the destination job. |
| `source_career_level` | `string` | Seniority level string of the origin job. |
| `target_career_level` | `string` | Seniority level string of the destination job. |

---

## Graph Metadata (`data/processed/job_graph_metadata.json`)

Metadata tracking embedding model configuration and edge construction parameters:

| Field | Type | Description |
|---|---|---|
| `schema_version` | `int` | Version identifier for the metadata schema. |
| `input_csv` | `string` | Path to the source input CSV. |
| `input_sha256` | `string` | SHA-256 hash of the input CSV file. |
| `job_count` | `int` | Total number of unique jobs processed. |
| `embedding_model` | `string` | Name of the embedding model used. |
| `semantic_source_columns` | `list<string>` | Columns included in `semantic_role_text`. |
| `excluded_from_semantic_similarity` | `list<string>` | Columns excluded from semantic role text. |
| `representation.strategy` | `string` | Description of embedding strategy. |
| `representation.model_token_limit` | `int` | Maximum token limit supported by the embedding model (8,192). |
| `representation.embedding_dimensions` | `int` | Dimensionality of generated vector embeddings (1,536). |
| `representation.long_texts_counted` | `int` | Count of job texts verified with token counting API. |
| `representation.maximum_counted_tokens` | `int` | Maximum observed token count among verified long texts. |
| `edge_rules.allowed_target_seniority_ranks` | `string` | Allowed target seniority constraints (`source rank or source rank + 1`). |
| `edge_rules.max_candidates_per_seniority_rank` | `int` | Maximum candidate edges retained per target seniority rank (default: 32). |
| `edge_rules.similarity_cutoff` | `null` | Minimum similarity threshold filter (currently unconstrained). |
| `edge_rules.ranking_score` | `string` | Exact formula used to compute `ranking_score`. |
| `edge_count` | `int` | Total number of directed edges generated. |

