# 03 — Score a directed job move

**What to build:** Given a source job and a target job, the model evaluates that proposed move using duties, skills, career level, and requirements. It returns a score and a short, source-backed reason.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Any two jobs in the collection can be considered, even when no saved browsing link joins them.
- [ ] Direction and relevant requirements affect whether a move may be traversed; similarity alone does not create an implausible shortcut.
- [ ] The result distinguishes a useful direct move from a move with important qualification gaps and cites the relevant posting fields.
