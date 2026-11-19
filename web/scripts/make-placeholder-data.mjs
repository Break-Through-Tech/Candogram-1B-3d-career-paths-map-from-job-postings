// Builds public/data/jobs.json from the cleaned postings CSV so the web app
// has real jobs to render before the embedding + UMAP pipeline exists.
//
// Input comes from the data_cleaning branch: run `python main.py` there to
// produce data/processed/jobs_clean_with_salary.csv.
//
// Coordinates here are PLACEHOLDERS: x/z cluster by job category, y is the
// seniority rank. Replace them with the model's output once it's ready
// (same JSON shape — see web/README.md).
//
// Usage: node scripts/make-placeholder-data.mjs

import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const INPUT = resolve(here, '../../data/processed/jobs_clean_with_salary.csv')
const OUTPUT = resolve(here, '../public/data/jobs.json')

if (!existsSync(INPUT)) {
  console.error(`Missing ${INPUT}\nRun \`python main.py\` on the data_cleaning branch first.`)
  process.exit(1)
}

function parseCsv(text) {
  const rows = []
  let row = []
  let field = ''
  let inQuotes = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (inQuotes) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++ }
      else if (c === '"') inQuotes = false
      else field += c
    } else if (c === '"') inQuotes = true
    else if (c === ',') { row.push(field); field = '' }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++
      row.push(field); rows.push(row); row = []; field = ''
    } else field += c
  }
  if (field || row.length) { row.push(field); rows.push(row) }
  return rows
}

// Deterministic pseudo-random in [-1, 1) so the layout is stable between runs.
function hash(str, salt) {
  let h = 2166136261 ^ salt
  for (let i = 0; i < str.length; i++) h = Math.imul(h ^ str.charCodeAt(i), 16777619)
  return ((h >>> 0) / 2 ** 32) * 2 - 1
}

const number = (value) => (value === '' ? null : Number(value))

const [header, ...records] = parseCsv(readFileSync(INPUT, 'utf8'))
const col = Object.fromEntries(header.map((name, i) => [name, i]))
const get = (r, name) => r[col[name]] ?? ''

const jobs = records
  .filter((r) => get(r, 'Job ID'))
  .map((r) => ({
    id: get(r, 'Job ID'),
    title: get(r, 'Business Title'),
    agency: get(r, 'Agency'),
    categories: get(r, 'job_categories').split('; ').filter(Boolean),
    career_level: get(r, 'Career Level'),
    seniority_rank: Number(get(r, 'seniority_rank')),
    salary_from: number(get(r, 'salary_from_annual')),
    salary_to: number(get(r, 'salary_to_annual')),
    salary_mid: number(get(r, 'salary_midpoint_annual')),
    min_education_rank: number(get(r, 'min_education_rank')),
    min_years_experience: number(get(r, 'min_years_experience')),
    license: get(r, 'license_or_cert_mentioned') === 'True',
  }))

const categories = [...new Set(jobs.map((j) => j.categories[0] ?? 'Other'))].sort()
for (const job of jobs) {
  const angle = (categories.indexOf(job.categories[0] ?? 'Other') / categories.length) * Math.PI * 2
  const spread = 1.6
  job.x = +(Math.cos(angle) * 6 + hash(job.title, 1) * spread).toFixed(3)
  job.z = +(Math.sin(angle) * 6 + hash(job.title, 2) * spread).toFixed(3)
  job.y = +(job.seniority_rank * 2 - 4 + hash(job.id, 3) * 0.4).toFixed(3)
}

writeFileSync(OUTPUT, JSON.stringify({ placeholder: true, jobs }))
console.log(`Wrote ${jobs.length} jobs across ${categories.length} categories to ${OUTPUT}`)
