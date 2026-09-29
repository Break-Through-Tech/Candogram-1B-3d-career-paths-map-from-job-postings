// Builds public/data/jobs.json from the raw NYC postings CSV so the web app
// has real titles to render before the embedding + UMAP pipeline exists.
//
// Coordinates here are PLACEHOLDERS: x/z cluster by Job Category, y is the
// seniority rank. Replace this file with the model's output once it's ready
// (same JSON shape — see web/README.md).
//
// Usage: node scripts/make-placeholder-data.mjs

import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const INPUT = resolve(here, '../../data/Jobs_NYC_Postings_20260608.csv')
const OUTPUT = resolve(here, '../public/data/jobs.json')

// Mirrors SENIORITY_MAP in src/preprocessing.py (data_eda branch).
const SENIORITY_MAP = {
  Student: 0,
  'Entry-Level': 1,
  'Experienced (non-manager)': 2,
  Manager: 3,
  Executive: 4,
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

const [header, ...records] = parseCsv(readFileSync(INPUT, 'utf8'))
const col = Object.fromEntries(header.map((name, i) => [name.trim(), i]))

const byId = new Map()
for (const r of records) {
  const id = r[col['Job ID']]
  if (!id || byId.has(id)) continue
  const rank = SENIORITY_MAP[r[col['Career Level']]]
  if (rank === undefined) continue
  byId.set(id, {
    id,
    title: r[col['Business Title']].replace(/\s+/g, ' ').trim(),
    category: (r[col['Job Category']] || 'Other').split(/[,&]/)[0].trim() || 'Other',
    agency: r[col['Agency']],
    career_level: r[col['Career Level']],
    seniority_rank: rank,
    salary_from: Number(r[col['Salary Range From']]) || null,
    salary_to: Number(r[col['Salary Range To']]) || null,
    salary_frequency: r[col['Salary Frequency']],
  })
}

const jobs = [...byId.values()]
const categories = [...new Set(jobs.map((j) => j.category))].sort()
for (const job of jobs) {
  const angle = (categories.indexOf(job.category) / categories.length) * Math.PI * 2
  const spread = 1.6
  job.x = +(Math.cos(angle) * 6 + hash(job.title, 1) * spread).toFixed(3)
  job.z = +(Math.sin(angle) * 6 + hash(job.title, 2) * spread).toFixed(3)
  job.y = +(job.seniority_rank * 2 - 4 + hash(job.id, 3) * 0.4).toFixed(3)
}

writeFileSync(OUTPUT, JSON.stringify({ placeholder: true, jobs }))
console.log(`Wrote ${jobs.length} jobs across ${categories.length} categories to ${OUTPUT}`)
