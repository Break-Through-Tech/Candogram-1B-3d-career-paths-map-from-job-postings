# Career Paths Map — web app

Interactive 3D map of NYC job postings built with [Vite](https://vite.dev) and [three.js](https://threejs.org).
Each point is a job; pick one (search or click) to see its posting details and a suggested path up through the seniority levels.

## Run it

```bash
cd web
npm install
npm run dev
```

`npm run build` outputs a static site to `web/dist/` that can be hosted anywhere (GitHub Pages, Netlify, etc.).

## Data

The app loads `public/data/jobs.json` and the matching job-ID-to-location map in
`public/data/locations.json`:

```json
{
  "placeholder": false,
  "jobs": [
    {
      "id": "780346",
      "title": "Public Health Inspector",
      "category": "Public Safety",
      "agency": "DEPT OF HEALTH/MENTAL HYGIENE",
      "career_level": "Entry-Level",
      "seniority_rank": 1,
      "salary_from": 53132,
      "salary_to": 61102,
      "salary_frequency": "Annual",
      "x": 1.23, "y": -2.0, "z": 4.56
    }
  ]
}
```

- `seniority_rank` uses the same 0–4 scale as `SENIORITY_MAP` in `src/preprocessing.py`.
- `x`, `y`, `z` are the 3D coordinates to plot. They should come from the model pipeline
  (sentence embeddings → UMAP to 3D). The app works with any coordinate scale, though
  roughly −10…10 matches the current camera setup.
- Set `"placeholder": true` to show the "placeholder layout" notice.

Until the model produces coordinates, generate a placeholder file from the raw CSV:

```bash
node scripts/make-placeholder-data.mjs
```

It groups points by job category (x/z) and stacks them by seniority (y).
The generator also writes the Work Location values to `public/data/locations.json`.
Each seniority layer can be filtered independently by posted salary range, location,
job category, and agency. Salary values retain the posting's frequency (for example,
annual or hourly) and are not converted between frequencies.

Upload a PDF or TXT resume to get local, keyword-based job recommendations. Resume
text is processed only in the browser and is not uploaded or saved. PDF files must
contain selectable text; scanned-image PDFs are not OCR-processed. Recommendations
show shared terms from the resume and public posting qualifications/preferred skills.
The optional graph filter limits visible jobs to the top 20 matches; existing layer
filters still apply. This is a heuristic, not an assessment of a candidate's suitability.

## How paths are computed

`src/paths.js` starts at the selected job and repeatedly steps to the nearest job (in 3D space)
at the next seniority rank, skipping ranks with no jobs. Once the embedding coordinates are in,
"nearest" means "most similar title/description", which gives the Entry Level → Senior progression
described in the challenge. This can later be swapped for neighbors precomputed in Python
(e.g. scikit-learn `NearestNeighbors` on the full embeddings) by adding them to `jobs.json`.

## Layout

| File | Purpose |
|------|---------|
| `src/main.js` | Loads data, wires up search, tooltip and the path panel |
| `src/scene.js` | three.js scene: instanced points, orbit controls, picking, path tube |
| `src/paths.js` | Career path algorithm |
| `scripts/make-placeholder-data.mjs` | Builds placeholder `jobs.json` from the raw CSV |
