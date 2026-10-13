# 02 — Resolve a selected or searched goal

**What to build:** A user clicks a job node or searches for a target role. The model returns an exact selected job or a short list of possible destination jobs for the user to choose from.

**Blocked by:** 00 — User profile embeddings (complete).

**Status:** incomplete — selected-ID lookup and candidate ranking exist; validated goal resolution and no-match handling do not.

- [x] A selected job ID resolves to that exact job and remains the route endpoint.
- [ ] Validate query-to-job relevance, including main duties, requested level, and negation.
- [ ] Present distinct choices for broad or ambiguous requests.
- [ ] Return an explicit no-match result when no suitable destination exists.

`src/goal_search.py` provides candidate ranking. Decisions and evaluation limits
are recorded in `MODEL_DECISIONS.md`.
