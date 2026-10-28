# Modeling decisions

Add a dated entry when a new modeling problem leads to a consequential choice. Record the problem, the chosen approach, the rejected alternative, and what would change the choice. Keep implementation steps in [MODEL_PLAN.md](MODEL_PLAN.md).

## 2026-09-28 — Find the fewest job changes to a selected goal

- **Problem:** A user may click a goal outside their nearby-job suggestions and ask for several paths from their current position.
- **Decision:** Treat the clicked job ID as the endpoint. Search directed job moves with breadth-first or bidirectional breadth-first search to find the minimum number of job changes. Rank and diversify the paths that use that minimum. Do not set a fixed four-move limit.
- **Instead of:** Restricting search to browsing suggestions, using 3D distance as a move rule, or using weighted K-shortest paths when the first objective is the fewest moves.
- **Revisit when:** User research changes the primary objective from minimum moves to minimum effort, or measured search performance calls for another algorithm. Move quality still controls which directed edges the search may use.

## 2026-10-27 — Add provisional qualification evidence to node transitions

- **Problem:** Selected-node exploration ranked outgoing jobs with the browsing score, which used role similarity, title overlap, category overlap, and civil-service-title equality but did not compare the target's qualification text with evidence in the source role.
- **Decision:** Keep the existing signals as candidate-transition features and add a small direct-text qualification-overlap component. Compare the target's `Minimum Qual Requirements` and `Preferred Skills` with the source's `selected_description` and `Preferred Skills`. Return the overlap and unevidenced target terms with each transition so the score remains inspectable.
- **Provisional weights:** role similarity 0.80, title overlap 0.08, same civil-service title 0.04, same category 0.03, qualification overlap 0.05.
- **Instead of:** Treating embedding similarity as career feasibility, adding a hand-written skills vocabulary, or claiming that unevidenced terms are definitely missing from the user's background.
- **Before/after smoke check:** On five selected nodes, the same five-candidate sets were returned. The qualification component changed ordering in several sets, including manager and software-development examples. This was a smoke comparison, not a relevance evaluation.
- **Revisit when:** Manual judgments show that generic qualification terms distort the score, or a structured requirement representation is shown to improve transition ranking.

## 2026-10-27 — Retrieve node-exploration candidates from the full collection

- **Problem:** The saved browsing graph retains only a bounded number of nearby jobs per allowed seniority level, so using it as the complete retrieval set could hide a plausible next job.
- **Decision:** For selected-node exploration, generate candidates from the full job collection, restricting only by the transition policy's allowed seniority offsets and move types. Keep saved-edge retrieval as an explicit baseline option for comparison.
- **Instead of:** Treating the precomputed browsing suggestions as the complete career-move set or using 3D display distance as a retrieval rule.
- **Smoke comparison:** A deterministic sample of 20 selected nodes produced valid, ordered, duplicate-free target IDs in all 20 cases. Full-collection retrieval considered an average of 848.9 eligible candidates versus 63.7 saved edges per node; the top five lists happened to match in all 20 cases. Seven of the 20 top-five lists contained repeated target business titles, so title diversity remains an open issue. This confirms implementation behavior, not relevance; manual judgments are still required.
- **Revisit when:** Full-collection latency becomes material, or evaluation shows that a smaller candidate-generation index preserves relevant transitions without reducing coverage.

## 2026-09-30 — Add annual full-time salary equivalents

- **Problem:** Source salary bounds use annual, hourly, and daily units, so salary ranges cannot be compared directly.
- **Decision:** Retain the three source salary fields and add `normalized_salary_frequency` plus full-time annual equivalents using 1 for annual rates, 2,080 for hourly rates, and 260 for daily rates. Leave annualized lower bounds null when the source lower bound is zero. When a daily-labelled posting and a posting with the same title, civil-service title, and salary bounds explicitly state an hourly rate, use `Hourly` for both normalized frequency and annualization while preserving the source frequency.
- **Instead of:** Replacing source salary values, inferring work schedules from free text, or annualizing a zero minimum as valid pay.
- **Revisit when:** The source provides verified work hours or days per year, or NYC compensation rules specify different standard annualization factors.

## 2026-09-30 — Use canonical multi-label job categories

- **Problem:** The source `Job Category` field combines multiple category labels with inconsistent separators. Commas also appear inside category names, so delimiter-based splitting is ambiguous.
- **Decision:** Preserve the raw field and map each value to every matching label among the 14 canonical categories by whole-phrase matching. Store the labels as a JSON array in `job_categories` and use label overlap for filters and graph category scoring. Keep raw `Job Category` in the Gemini embedding input.
- **Instead of:** Splitting on punctuation, replacing the source category with a single label, or changing job embeddings for a filter-and-scoring feature.
- **Revisit when:** A source category cannot be mapped, the category taxonomy changes, or review finds a label assignment error.

## 2026-09-30 — Use existing qualification text first

- **Problem:** The cleaned jobs already retain minimum qualifications and preferred skills, but no user-to-job comparison exists yet.
- **Decision:** Compare profile facts directly with those source text fields first. Do not create a duplicate set of extracted requirement fields until evaluation shows that direct comparison misses important gaps.
- **Instead of:** Running an AI extraction pass over the entire job corpus before measuring whether the structured fields are needed.
- **Supersedes:** An earlier plan to extract structured required and preferred items, with evidence, from `Minimum Qual Requirements` and `Preferred Skills`. Any future extraction must still exclude profile PII from model requests.
- **Revisit when:** Reviewed profile-to-job matches show that raw requirement text cannot support useful qualification comparisons.

## 2026-09-30 — Defer posting windows and position counts

- **Problem:** Posting dates vary across versions of the same job, while position counts include an unexplained `9999` value.
- **Decision:** Exclude posting dates and position counts from the cleaned model dataset for this pass. Keep the existing source fields available for later review.
- **Instead of:** Collapsing multiple posting windows into one job-level open/closed value or treating `9999` as a verified vacancy count.
- **Revisit when:** The prototype needs vacancy filtering and the source semantics and posting-window grain are established.

## 2026-10-06 — Embed selected work passages instead of full descriptions

- **Problem:** Full descriptions mix actual duties with agency background, benefits, and hiring instructions. Source matching alone does not show whether selected passages preserve role meaning or improve nearby-job retrieval.
- **Decision:** Use Gemini 3.8 Flash to select verbatim work passages from every description. The prompt explains the embedding and career-map purpose, preserves all important work and role context without a passage-count target, and reads the whole description. Embed the selected passages with the business title, civil-service title, and raw category, and retain original descriptions beside them. Invalidate saved extractions when the prompt, model, schema, or source input changes. Gemini 2.5 Flash was unavailable to new users, so the pipeline uses the API's recommended Gemini 3.8 Flash.
- **Source matching:** Accept a passage only when it is an exact source substring. When model output differs only in whitespace, restore the original source span. Keep raw model passages for inspection and reject all other differences. In the revised pilot, nine passages needed whitespace restoration; one with changed quotation marks was rejected and its job flagged.
- **Fallback:** If any passage is rejected or no usable text remains, flag the job and embed its original description. New jobs not yet processed also use the original. In this snapshot, 1,200 jobs use selected passages and 28 use the fallback. Extraction outputs and flagged jobs are saved under `data/processed/description_full/`.
- **Evidence:** A method-blinded automated evaluator compared top-five neighbors for 40 pilot jobs and 40 fresh jobs selected with seed 2026 against full-text, selected-text, and title-only indexes. Across the 80 queries, mean relevance rose from 1.330 (full descriptions) to 1.473 (selected passages) on a 0–2 scale; 31 jobs improved, 39 tied, and 10 worsened. The fresh cohort improved 12, tied 23, and worsened five. These are automated judgments, not independent human validation.
- **Pilots:** The first 40-job pilot sampled two jobs per canonical category, the Systems Developer example, and short and long descriptions. All 40 completed and 289 passages matched their sources exactly, but neighbor relevance moved only from 1.275 to 1.340 (11 improved, 16 tied, 13 worsened) and six extractions omitted important detail, so full descriptions stayed the default. Rerunning the same 40 jobs with the revised prompt, an automated review rated all 40 as preserving defining work; relevance moved from 1.265 to 1.345 (14 improved, 16 tied, 10 worsened) with a 45% median text reduction.
- **Rollout:** The default graph reused matching Gemini vectors and replaced the old vectors and links only after verification: 1,228 normalized vectors matched the validated collection, and 77,278 rebuilt links had unique endpoints.
- **Instead of:** Rewriting descriptions, extracting structured qualifications in this pass, treating exact quotes or a small average gain as proof that trimming improves recommendations, copying an embedding file without changing its generating pipeline, or deleting old vectors before verifying the replacement.
- **Revisit when:** New data or independent human review shows omitted duties, irrelevant passages, or a better representation of a job.

## 2026-10-06 — Embed work profiles and goal queries within a session

- **Problem:** The model has job vectors but no inputs for a person's current work or desired destination.
- **Decision:** Use separate, extensible Python data models for work profiles and natural-language goal queries. The query is the goal feature, not a separate search beside a saved goal. Keep interests with the goal. Select embedding fields explicitly in text preparation. Education, licenses, and experience years remain separate facts.
- **Embedding settings:** Use the existing Gemini Embedding 2 model with 1,536 dimensions. Share settings with job embeddings. Apply the official text search-query prefix to user inputs. Preserve existing job vectors; a paired query/document-format comparison remains future evaluation work. Job and user text share one embedding helper; it trusts SDK responses and checks only the input token limit, because Gemini silently truncates longer input.
- **Cache:** Keep vectors in memory in one `EmbeddingSession` per user session. Key them by input type and prepared text; model settings are constant within a session. Reuse exact cached results without renormalizing them. Clear the cache at session end; the app must also release its own references.
- **Privacy:** Accept only work-related fields. Do not log or save user text or vectors: user-input dataclasses disable `repr`, and embedding API errors are re-raised without the SDK error chain. Do not build automatic PII redaction in this pass. The calling app must supply PII-free text; this module does not detect personal details in free text. Verification uses synthetic inputs only.
- **Instead of:** Combining current work and desired work into one vector, automatically embedding every new model field, persisting user embeddings with shared job artifacts, or implementing job ranking in the embedding ticket.
- **Observed:** Six live synthetic embedding requests returned valid normalized vectors, including one long input checked with `count_tokens`. Repeated calls reused the cache without new API calls. Offline checks exercised edits, session cleanup and isolation, empty inputs, limits, and sanitized API errors.
- **Matching limit:** Developer and audit profiles retrieved jobs in their work domains. A software-engineering internship query retrieved civil-engineering internships. Four additional format probes showed that removing the query prefix did not resolve the domain mismatch. These are smoke checks, not a relevance benchmark. Goal resolution must add role/title evidence and reject unsuitable matches.
- **Revisit when:** Evaluation supports a different text format, or repeat use justifies persistent user-specific storage with access and deletion rules.

## 2026-10-06 — Keep goal search as candidate retrieval

- **Decision:** Combine semantic and keyword ranks across the full collection. Keep profile fit separate. Remove hand-written career filters and do not label keyword coverage as suitability.
- **Limit:** Goal relevance, diversity, and no-match handling remain open. Browsing seniority restrictions and weights remain a separate policy.

## 2026-10-06 — Remove the rejected reranker experiment

- **Observed:** MiniLM did not improve a tiny agent-judged pilot: development nDCG was 0.8754 for hybrid versus 0.8314 for the model; held-out values were both 0.9949. These scores covered only 3–5 judged pairs per goal, not full result-list relevance.
- **Decision:** Remove the model wrapper, evaluation script, synthetic judgments, report, and optional dependencies. The pilot does not validate either ranking approach or an abstention threshold.
