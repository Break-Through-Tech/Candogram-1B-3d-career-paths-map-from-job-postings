# 00 — User profile embeddings

**What to build:** Convert a work profile and a natural-language goal query into
separate embeddings for semantic matching. The goal query is the target-role
search, not a separate saved-goal feature.

**Blocked by:** None.

**Status:** complete — model-layer checks passed; app integration is separate.

- [x] Use small, extensible work-profile, work-experience, and goal-query models.
  New fields do not enter embedding text automatically.
- [x] Embed stated work and skills separately from desired work and interests.
  Retain education, licenses, and experience years as separate facts.
- [x] Use Gemini Embedding 2 with the same 1,536 dimensions as job vectors.
- [x] Cache only within one user session. Reuse unchanged prepared inputs;
  regenerate when prepared text or embedding settings change.
- [x] Reject empty inputs and invalid or truncated model responses.
- [x] Keep user inputs and vectors out of logs, files, and shared job artifacts.
  Use synthetic profiles for verification; do not add automatic PII redaction.
- [x] Verify real response dimensions, normalized vectors, cache reuse, and a
  long input. Run failure and cache-boundary checks without adding test files.

**Implementation:** `src/user_profile.py`, `src/profile_embeddings.py`, and
`src/embedding_config.py`. See [the usage guide](../../../docs/user-profile-embeddings.md).

**Follow-up:** Tickets 01 and 02 own recommendation ranking and goal resolution.
Vector-only matching can confuse internship domains and does not establish
qualification fit. The app must supply PII-free text, validate incoming request
data, and create and clear one cache per user session.
