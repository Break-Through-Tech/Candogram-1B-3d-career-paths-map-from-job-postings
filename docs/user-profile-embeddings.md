# Embed a work profile and a goal query

Use `src.profile_embeddings` to create separate vectors for current work and
desired work. The goal query is the user's natural-language target-role search.
There is no separate saved-goal model.

## Run a synthetic example

1. Run `uv sync` from the repository root.
2. Supply `GEMINI_API_KEY` in your environment or the ignored root `.env` file.
3. Run this example from the repository root. It makes two embedding requests.

```sh
uv run python - <<'PY'
from dotenv import load_dotenv
from google import genai

from src.profile_embeddings import EmbeddingSession
from src.user_profile import GoalQuery, WorkExperience, WorkProfile

load_dotenv(".env")
profile = WorkProfile(
	current_role="Junior software developer",
	work_summary="Build Python APIs and maintain SQL reporting tools.",
	skills=("Python", "SQL", "Git"),
	experience=(
		WorkExperience(
			role="Software development intern",
			work_summary="Build API endpoints and review pull requests.",
			years=0.5,
		),
	),
	education=("Bachelor's degree in computer science",),
)
goal = GoalQuery(
	text="I want a software engineering role focused on backend systems.",
	interests=("Public services",),
)

with genai.Client() as client:
	with EmbeddingSession(client) as session:
		work = session.embed_profile(profile)
		target = session.embed_goal(goal)
		assert session.embed_profile(profile) is work
		assert session.embed_goal(goal) is target
		print(work.model, work.dimensions, work.input_type)
		print(target.model, target.dimensions, target.input_type)
		print("Repeated inputs reused the session cache.")
PY
```

Expected output:

```text
gemini-embedding-2 1536 profile
gemini-embedding-2 1536 goal
Repeated inputs reused the session cache.
```

## Connect the session to the app

- Create one `EmbeddingSession` per user session. Do not share it across users.
- Pass a caller-owned Gemini client. The embedding session does not close it.
- Call `embed_profile` or `embed_goal` after input edits. Unchanged prepared text
  reuses its vector. Changed text makes a new request.
- Keep the session instance alive between requests from that user.
- Call `clear()` when the user session ends. A context manager also clears the
  cache on exit, including when an exception occurs.
- Release any profile, query, and result references held by the app at session
  end. Clearing the cache does not erase copies held elsewhere.
- Do not write inputs or vectors to files, application logs, Git, or the shared
  job artifacts. Supply only work-related, PII-free text. This module does not
  detect or remove personal details inside free text.
- Validate incoming API or UI data before constructing these typed Python
  models. They are dataclasses, not HTTP request validators.

## Extend the inputs

Add fields to `WorkProfile`, `WorkExperience`, or `GoalQuery` as needed. Keep
embedding text selection in `prepare_profile_text` and `prepare_goal_text`.
New model fields do not enter embedding requests automatically.

Approve a new field before adding it to text preparation. Increase
`TEXT_FORMAT_VERSION` when the text format changes.

Education, licenses, and experience years remain separate profile facts.
Changing only these facts does not regenerate the profile vector.
Qualification checks and job ranking are separate tickets.

## Use the vectors for matching

Read `UserEmbedding.values` for the normalized vector. Its metadata identifies
the input type, model, dimensions, text-format version, and cache key.
The cache key includes all of these settings and the prepared text.

The model and dimensions match the existing job vectors. User inputs use the
[documented search-query prefix](https://ai.google.dev/gemini-api/docs/embeddings#task-types).
This ticket does not change the job vectors or claim that matching qualifications
can be inferred from vector similarity.
