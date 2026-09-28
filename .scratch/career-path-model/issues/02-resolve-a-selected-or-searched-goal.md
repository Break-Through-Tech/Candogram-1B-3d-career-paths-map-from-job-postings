# 02 — Resolve a selected or searched goal

**What to build:** A user clicks a job node or searches for a target role. The model returns an exact selected job or a short list of possible destination jobs for the user to choose from.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] A selected job ID resolves to that exact job and remains the route endpoint.
- [ ] A typed or natural-language role request retrieves and ranks destination jobs using role meaning and title evidence.
- [ ] Ambiguous requests present distinct choices; a request without a suitable match does not silently select an unrelated job.
