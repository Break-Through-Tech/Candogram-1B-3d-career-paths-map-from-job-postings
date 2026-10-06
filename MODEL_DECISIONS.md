# Modeling decisions

Add a dated entry when a new modeling problem leads to a consequential choice. Record the problem, the chosen approach, the rejected alternative, and what would change the choice. Keep implementation steps in [MODEL_PLAN.md](MODEL_PLAN.md).

## 2026-09-28 — Find the fewest job changes to a selected goal

- **Problem:** A user may click a goal outside their nearby-job suggestions and ask for several paths from their current position.
- **Decision:** Treat the clicked job ID as the endpoint. Search directed job moves with breadth-first or bidirectional breadth-first search to find the minimum number of job changes. Rank and diversify the paths that use that minimum. Do not set a fixed four-move limit.
- **Instead of:** Restricting search to browsing suggestions, using 3D distance as a move rule, or using weighted K-shortest paths when the first objective is the fewest moves.
- **Revisit when:** User research changes the primary objective from minimum moves to minimum effort, or measured search performance calls for another algorithm. Move quality still controls which directed edges the search may use.

## 2026-09-30 — Add annual full-time salary equivalents

- **Problem:** Source salary bounds use annual, hourly, and daily units, so salary ranges cannot be compared directly.
- **Decision:** Retain the three source salary fields and add `normalized_salary_frequency` plus full-time annual equivalents using 1 for annual rates, 2,080 for hourly rates, and 260 for daily rates. Leave annualized lower bounds null when the source lower bound is zero. When a daily-labelled posting and a posting with the same title, civil-service title, and salary bounds explicitly state an hourly rate, use `Hourly` for both normalized frequency and annualization while preserving the source frequency.
- **Instead of:** Replacing source salary values, inferring work schedules from free text, or annualizing a zero minimum as valid pay.
- **Revisit when:** The source provides verified work hours or days per year, or NYC compensation rules specify different standard annualization factors.

## 2026-09-30 — Add canonical multi-label job categories

- **Problem:** The source `Job Category` field combines multiple category labels in strings with inconsistent separators.
- **Decision:** Preserve the raw field and map each value to one or more of the 14 canonical categories for filtering and graph scoring. Match whole category phrases, serialize labels as JSON, and keep raw `Job Category` in the Gemini embedding input.
- **Instead of:** Splitting on punctuation or replacing the source category with a single label.
- **Revisit when:** The category taxonomy changes or review finds category assignments that do not match the source.

## 2026-09-30 — Extract requirements with AI (superseded)

- **Problem:** Skills, education, experience, and licenses are embedded in free-text qualification fields.
- **Decision:** Use AI to extract structured requirements from `Minimum Qual Requirements` and `Preferred Skills`. Preserve the source text, distinguish required from preferred items, and retain evidence for each extraction. Exclude profile PII from model requests.
- **Instead of:** Treating raw text as structured values or relying only on string patterns.
- **Revisit when:** Extraction review shows the chosen output fields, labels, or AI model do not support reliable profile matching.

## 2026-09-30 — Use existing qualification text first

- **Problem:** The cleaned jobs already retain minimum qualifications and preferred skills, but no user-to-job comparison exists yet.
- **Decision:** Compare profile facts directly with those source text fields first. Do not create a duplicate set of extracted requirement fields until evaluation shows that direct comparison misses important gaps.
- **Instead of:** Running an AI extraction pass over the entire job corpus before measuring whether the structured fields are needed.
- **Revisit when:** Reviewed profile-to-job matches show that raw requirement text cannot support useful qualification comparisons.

## 2026-09-30 — Use canonical categories for filters and scoring

- **Problem:** Raw category values combine multiple category names and contain punctuation that makes delimiter-based splitting ambiguous.
- **Decision:** Map source values to the 14 known category phrases, store all matching labels in `job_categories`, and use label overlap for category scoring. Preserve raw category text in the Gemini role embedding.
- **Instead of:** Splitting on commas or changing job embeddings for a filter-and-scoring feature.
- **Revisit when:** A source category cannot be mapped, the category set changes, or review finds a label assignment error.

## 2026-09-30 — Defer posting windows and position counts

- **Problem:** Posting dates vary across versions of the same job, while position counts include an unexplained `9999` value.
- **Decision:** Exclude posting dates and position counts from the cleaned model dataset for this pass. Keep the existing source fields available for later review.
- **Instead of:** Collapsing multiple posting windows into one job-level open/closed value or treating `9999` as a verified vacancy count.
- **Revisit when:** The prototype needs vacancy filtering and the source semantics and posting-window grain are established.

## 2026-10-06 — Pilot source-grounded duty extraction

- **Problem:** Full descriptions mix actual duties with agency background, benefits, and hiring instructions.
- **Decision:** Extract verbatim duty passages for 40 jobs with Gemini 3.8 Flash. Include two sampled jobs for each canonical category, the Systems Developer example, and short and long descriptions. Preserve descriptions and verify each passage by exact substring matching. Save the sample, extraction instructions, model, and results separately from the existing job representations.
- **Instead of:** Rewriting descriptions, replacing embeddings immediately, or extracting structured qualifications in this pass.
- **Observed:** All 40 jobs completed; 289 passages matched their source descriptions exactly. This establishes source matching, not duty completeness or better recommendations. Gemini 2.5 Flash rejected the first request as unavailable to new users, so the pilot used the API's recommended Gemini 3.8 Flash.
- **Revisit when:** Human review identifies omitted duties or irrelevant passages, or a neighbor comparison shows no improvement over full-description and title-only inputs.

## 2026-10-06 — Keep full descriptions after the first extraction pilot

- **Problem:** Source matching alone does not show whether selected duties preserve role meaning or improve nearby-job retrieval.
- **Decision:** Keep full-description embeddings as the default. Compare the 40 pilot queries against the fixed 1,228-job index and use a separate, method-blinded automated neighbor evaluator. Preserve category and title fields when replacing description text to isolate the change.
- **Observed:** The final mean relevance score rises from 1.275 to 1.340 on a 0–2 scale. Duties queries improve 11 jobs, tie 16, and worsen 13. Six extractions omit important detail. These results do not justify applying the current prompt to the whole corpus.
- **Instead of:** Treating exact quotes or a small average gain as proof that description trimming universally improves recommendations.
- **Revisit when:** Instructions preserve specialties and role context, and a repeated comparison plus independent human review supports rollout.
- **Prompt revision:** Explain the embedding and career-map purpose, preserve all important work and role context without a passage-count target, and check the whole description. Invalidate saved extractions when the prompt, model, schema, or source input changes.
- **Revised pilot:** Deleted the old outputs and reran the same 40 jobs. The automated review rated all 40 as preserving defining work. The separate blinded neighbor score was 1.345 for selected work passages versus 1.265 for full text. Selected queries improved 14 jobs, tied 16, and worsened 10. The median text reduction was 45%. These are automated pilot results, not independent human approval.
- **Source matching:** Restore original source spans when model output differs only in whitespace. Keep raw model passages for inspection and reject all other differences. Nine passages needed whitespace restoration; one passage with changed quotation marks remains rejected and its job is flagged for review.

## 2026-10-06 — Process all descriptions and compare complete indexes

- **Decision:** Process all 1,228 descriptions with the revised embedding-aware prompt. Keep original descriptions. If any passage is rejected or no usable text remains, flag the job and retain its original description in the experimental collection.
- **Comparison:** Build separate full-text, cleaned-text, and title-only indexes. Compare top-five neighbors for the 40 pilot jobs and 40 fresh jobs selected with seed 2026. Use the separate method-blinded automated evaluator and report the fresh cohort separately.
- **Observed:** 1,200 jobs use extracted text; 28 use original-text fallbacks. Accepted passages match their sources exactly. Across 80 queries, mean relevance rises from 1.330 to 1.473 on a 0–2 scale. Cleaned neighbors improve 31 jobs, tie 39, and worsen 10. In the fresh cohort, they improve 12, tie 23, and worsen five.
- **Limit:** These are automated judgments, not independent human validation. Existing default embeddings and graph outputs remain unchanged. The cleaned representation artifact and the flagged jobs are saved under `data/processed/description_full/`.

## 2026-10-06 — Use selected descriptions in the default job graph

- **Problem:** The full run produced better-performing embeddings from selected work passages, but the default graph command still embedded original descriptions.
- **Decision:** Make prepared descriptions the default embedding input. Retain original descriptions beside them. Use the original for the 28 flagged jobs and for new jobs not yet processed. Reuse matching Gemini vectors, rebuild browsing links, then replace the old default vectors and links.
- **Evidence:** The model-blinded comparison scored cleaned neighbors 1.473 versus 1.330 for full descriptions on 80 queries. The replacement contains 1,228 normalized vectors; all match the validated cleaned collection, and 77,278 rebuilt links have unique endpoints.
- **Instead of:** Copying an embedding file without changing its generating pipeline, or deleting old vectors before verifying the replacement.
- **Revisit when:** New data or independent review changes which passages best represent a job.
