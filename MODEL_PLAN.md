# Career-path model plan

## Starting point

- `src/preprocessing.py` produces one record per job with source text, career level, categories, salary, and qualifications. `src/job_descriptions.py` selects source-grounded work passages. `src/job_graph.py` embeds those passages with Gemini Embedding 2 and saves nearby-job suggestions for browsing.
- The browsing suggestions are **not** the complete set of possible career moves. This branch owns data and modeling outputs, not the platform UI. Record new modeling decisions in [MODEL_DECISIONS.md](MODEL_DECISIONS.md).
- Local implementation tickets live in [.scratch/career-path-model/issues](.scratch/career-path-model/issues).
- Keep `Job Category` as source text and add multi-label values from the 14 canonical categories for filters and scoring. Do not replace category text in the embedding input. Match profile requirements directly against the existing `Minimum Qual Requirements` and `Preferred Skills` text before adding structured extraction.
- Leave position counts and posting-date windows out of the model dataset for this pass.

## Build the personalized model

1. **Represent a profile and a request.** Accept a current role or work summary, plus any stated skills, experience, education, and licenses. Exclude names, contact details, and other profile PII from model requests. A selected posting gives an exact goal ID; search text gives candidate goal jobs; a request without a goal asks for career directions. Resolve ambiguity before selecting a target. Embed relevant non-PII work and skill details with Gemini Embedding 2. Keep qualifications as separate facts.
2. **Recommend relevant jobs now.** Compare the profile embedding with the full job collection. Combine semantic similarity with title and skill matches, career level, and explicit requirements. Rank a short set of relevant jobs and give a concise reason for each. Do not restrict retrieval to the saved browsing suggestions.
3. **Use existing job requirements.** Compare user profile facts directly with `Minimum Qual Requirements` and `Preferred Skills`. Preserve those source texts. Add AI extraction only if evaluation shows that direct text comparison misses important qualification gaps.
4. **Score possible career moves.** Build a directed job-to-job move scorer from role similarity, shared categories, existing skills and qualification text, and career level. Use job IDs as nodes. Keep browsing suggestions separate from edges considered during a goal-directed search. Define move quality before setting any cutoff; a shortcut must not win merely because it uses fewer steps.
5. **Find paths to a selected goal.** Anchor the user's starting position in relevant jobs. Search directed moves toward the selected target with breadth-first or bidirectional breadth-first search. Find the **minimum number of job changes for that request**, not an arbitrary four-step maximum. Exclude cycles. Rank and diversify paths with that minimum length using move quality and profile fit; show several distinct routes when they exist. If the current move policy cannot reach the goal, say so rather than invent a connection.
6. **Show useful evidence.** For each recommended job and route, show the main matching skills or duties and any important qualification gaps. Keep known, missing, and unprovided facts distinct. An intermediate posting does not itself add skills to the user's profile.
7. **Improve with data.** Judge present-job recommendations, goal matches, and complete routes on a manageable set of profiles and goals. Measure candidate coverage separately from ranking and route quality. Refine move rules and scores, then train a small ranker when judgments or user feedback support it. Add transition-based learning if real career histories become available. Do not add test files.
8. **Export for the 3D map.** Publish stable job IDs, display coordinates, nearby browsing links, selected routes, and their reasons. Use the richer job representation for ranking and path search; use 3D distance only for display.

## Research behind the choices

- [Meta on retrieval followed by ranking](https://engineering.fb.com/2023/08/09/ml-applications/scaling-instagram-explore-recommendations-system/) and [LinkedIn on job matching](https://arxiv.org/html/2402.13435) motivate separate candidate retrieval and personalized ranking.
- [LinkedIn's Skills Graph](https://www.linkedin.com/blog/engineering/skills-graph/building-linkedin-s-skills-graph-to-power-a-skills-first-world) motivates distinct skills held by a person and skills required by a job.
- [NetworkX shortest-path algorithms](https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html) describe the minimum-hop search. The application must still define which proposed job moves may be traversed.
