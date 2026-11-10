# Agent rules

## Engineering style

- Write clean, direct code that completes the requested job.
- Use comments only for non-obvious decisions. Keep self-evident code uncommented.
- Do not add tests or smoke-test scripts unless requested. Use only the checks needed to verify the work.
- Use data and evaluation for career relevance, not hand-written career vocabularies or hidden query filters.
- Do not add Markdown documentation files unless requested.
- Embedding requests go through `embed_text` in `src/embedding_config.py`. Callers add their own text formatting, such as `QUERY_TASK_PREFIX`, before calling it.
- Reuse an existing tokenizer or text normalizer before writing a new one. Merging the existing ones changes BM25 scores or edges, so treat that as a model change.
- Prefer vectorized NumPy/pandas over per-row or per-pair Python loops across the full job collection. Build detailed rows only for results you keep.

## Validation

Validate each input boundary once, where the data enters. The boundaries are:

- Raw postings (`data/Jobs_NYC_Postings_*.csv`), validated in `src/preprocessing.py`.
- User-supplied `WorkProfile` and `GoalQuery` text, including emptiness and model input limits.
- CLI arguments and public method parameters (limits, selected job IDs), checked where first used.
- LLM-generated text, including cached responses in `results.jsonl`, which `src/job_descriptions.py` revalidates against the current source description on every run.

Everything else is trusted:

- Each internal artifact (`jobs_clean.csv`, `prepared_jobs.csv`, `flagged_jobs.csv`, `job_representations.parquet`, `job_move_edges.parquet`, `job_graph_metadata.json`) has one owner: the module that writes it. Consumers rely on that contract and do not re-check its columns, IDs, dimensions, norms, or finiteness.
- SDK return values (`google-genai`, including embedding vectors, `pandas`, `numpy`) are trusted. Let SDK exceptions propagate unless a recorded decision says otherwise.

Keep a cross-stage check only when its failure would otherwise be silent: an embedding-model mismatch between job and query vectors, a stale upstream artifact, or a cache fingerprint. Keep a check only if the code path can produce the failure; confirm SDK fields against the installed types or official docs (for example, fields documented as Enterprise-only are always empty on the Gemini Developer API).

## Caches and long runs

- Key a cache on exactly what can vary during its lifetime. An in-memory session cache does not key on process constants such as `MODEL_NAME`. A persistent cache keys on content plus the settings that produced it.
- Derive artifact metadata from the data, never from cache history.
- New remote or paid batch runs persist each completed result immediately so an interrupted run resumes, then compact or rewrite the output once at the end, atomically.

## Model changes and documentation

- A change to embedding input text, scoring weights, or ranking order is a model change. Record it in `MODEL_DECISIONS.md` with a before/after evaluation.
- A refactor keeps artifact values unchanged: identical vectors, edges, and rankings. Dropping, renaming, or reordering columns is a schema change: update `DATA_DICTIONARY.md` and bump `schema_version` in `job_graph_metadata.json`.
- A documented privacy or safety measure (for example `repr=False` on user-input dataclasses) is removed only together with an update to the decision that records it.
- When a column, metadata field, or behavior changes, update `DATA_DICTIONARY.md` and any related `.scratch` ticket in the same change, plus `MODEL_DECISIONS.md` for model changes.

## Verifying pipeline changes

`main.py` runs preprocessing only, and every stage overwrites its outputs. Before rerunning stages, copy `data/processed/` elsewhere, then compare against the copy. To guarantee no API calls, run with `GEMINI_API_KEY=` and `GOOGLE_API_KEY=` set empty:

- `uv run python main.py`
- `uv run python -m src.job_descriptions` (without `--generate`)
- `uv run python -m src.job_graph` (calls Gemini for any role text missing from the existing parquet)
- Construct `GoalSearch()`; `rank_candidates` needs an embedding client or a stand-in session.

## Services and APIs

Before using a service or API, fetch and read its current official documentation for the operation you will perform. Confirm the supported model or API version, request format, authentication, and relevant limits before making calls.

If documentation is unavailable, report the blocker and ask how to proceed before making calls.
