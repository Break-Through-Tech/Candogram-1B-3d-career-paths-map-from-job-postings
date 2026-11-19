# Career Paths Map — web app

Interactive 3D map of NYC job postings built with [Vite](https://vite.dev) and [three.js](https://threejs.org).
Each point is a job; pick one (search or click) to see a suggested path through the seniority levels.

On first visit a short wizard asks what the student is trying to do (explore, reach a target job, or grow
from a current job), plus their education, experience and salary needs. The answers set up the map:

- **Exploring** → filters to the chosen fields and lists entry-level jobs they meet the listed minimums for.
- **Job in mind** → shows a "how to get there" path ending at that job, marking where they could start.
- **Grow from current job** → shows a "where it can lead" path from that job.

Every step shows salary, minimum education, years of experience and whether a license is needed, with
badges for what the student is missing. Filters (industry, minimum salary, "only jobs I qualify for",
hide license-required jobs) dim the map and constrain paths. A "By level" section narrows each seniority
level separately (pay range, field, agency) and shows how many jobs remain at that level. Answers are
remembered in the browser.

## Run it

```bash
cd web
npm install
npm run dev
```

`npm run build` outputs a static site to `web/dist/` that can be hosted anywhere (GitHub Pages, Netlify, etc.).

## Data

The app loads `public/data/jobs.json`:

```json
{
  "placeholder": false,
  "jobs": [
    {
      "id": "780346",
      "title": "Public Health Inspector",
      "agency": "DEPT OF HEALTH/MENTAL HYGIENE",
      "categories": ["Public Safety, Inspections, & Enforcement"],
      "career_level": "Entry-Level",
      "seniority_rank": 1,
      "salary_from": 53132,
      "salary_to": 61102,
      "salary_mid": 57117,
      "min_education_rank": 1,
      "min_years_experience": 3,
      "license": false,
      "x": 1.23, "y": -2.0, "z": 4.56
    }
  ]
}
```

- Fields come from `data/processed/job_representations.parquet`; `next` / `prev` (not shown above) are job IDs
  of the strongest one-level-up / one-level-down moves from `job_move_edges.parquet`.
- `seniority_rank` uses the same 0–4 scale as `SENIORITY_MAP` in `src/preprocessing.py`.
- Salaries are yearly. `min_education_rank` is 0 (none) to 5 (doctorate/professional); it and
  `min_years_experience` are `null` when the posting doesn't list them.
- `x`, `y`, `z` are a 3D UMAP of the Gemini job embeddings, scaled to roughly −10…10 to match the camera setup.
- Set `"placeholder": true` to show the "placeholder layout" notice.

Regenerate it from the model artifacts (needs `pandas`, `pyarrow`, `numpy` and `umap-learn`):

```bash
python web/scripts/build-job-data.py
```

Education, experience and license fields are carried over from the existing `jobs.json` by job ID.
`scripts/make-placeholder-data.mjs` is the older category-grid layout from the cleaned CSV and overwrites `jobs.json`.

## How paths are computed

`src/paths.js` starts at the selected job and, for each seniority level up ("where it leads") or down to
Entry-Level ("how to get here"), takes the model's strongest move (`next` / `prev`) that is still visible
under the current filters. If none qualifies, it steps to the nearest job in 3D space at that level,
skipping levels with no jobs. With placeholder coordinates, steps also prefer jobs in the same field.

## Layout

| File | Purpose |
|------|---------|
| `src/main.js` | Loads data, app state, filters (including per-level), search, path and suggestion panels |
| `src/wizard.js` | Onboarding questions |
| `src/profile.js` | Student answers and "do I meet the minimums?" checks |
| `src/scene.js` | three.js scene: instanced points, orbit controls, picking, filtering, path tube |
| `src/paths.js` | Career path algorithm |
| `src/format.js` | Salary and text formatting |
| `scripts/build-job-data.py` | Builds `jobs.json` from the embeddings and move graph |
| `scripts/make-placeholder-data.mjs` | Older placeholder layout from the cleaned CSV |
