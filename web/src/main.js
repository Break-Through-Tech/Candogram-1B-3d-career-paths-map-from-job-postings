import './style.css'
import { createScene, SENIORITY_COLORS } from './scene.js'
import { careerPath, SENIORITY_LABELS } from './paths.js'
import { matchResumeToJobs, readResume } from './resume.js'

const $ = (selector) => document.querySelector(selector)

const baseUrl = import.meta.env.BASE_URL
const [{ jobs, placeholder }, locations] = await Promise.all([
  fetch(`${baseUrl}data/jobs.json`).then((r) => r.json()),
  fetch(`${baseUrl}data/locations.json`).then((r) => r.json()),
])
for (const job of jobs) job.location = locations[job.id] || job.location || ''

$('#placeholder-note').hidden = !placeholder

$('#legend').innerHTML = SENIORITY_LABELS.map(
  (label, rank) =>
    `<li><span class="swatch" style="background:${SENIORITY_COLORS[rank]}"></span>${label}</li>`,
).join('')

const filtersByRank = new Map()
for (const rank of new Set(jobs.map((job) => job.seniority_rank))) {
  filtersByRank.set(rank, { minSalary: '', maxSalary: '', location: '', category: '', agency: '' })
}

const layerFilters = $('#layer-filters')
layerFilters.insertAdjacentHTML('beforeend', [...filtersByRank.keys()].sort((a, b) => a - b).map((rank) => {
  const layerJobs = jobs.filter((job) => job.seniority_rank === rank)
  const label = SENIORITY_LABELS[rank]
  const options = (field) => [...new Set(layerJobs.map((job) => job[field]).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b))
    .map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`)
    .join('')
  return `
    <details class="layer-filter" data-rank="${rank}">
      <summary>
        <span class="swatch" style="background:${SENIORITY_COLORS[rank]}"></span>
        <span>${escapeHtml(label)}</span>
        <span class="layer-count" data-count="${rank}"></span>
      </summary>
      <div class="filter-fields">
        <label>Salary range (as posted)
          <span class="salary-inputs">
            <input data-filter="minSalary" type="number" min="0" placeholder="Min" aria-label="Minimum salary for ${escapeHtml(label)}">
            <input data-filter="maxSalary" type="number" min="0" placeholder="Max" aria-label="Maximum salary for ${escapeHtml(label)}">
          </span>
        </label>
        <label>Location
          <select data-filter="location"><option value="">All locations</option>${options('location')}</select>
        </label>
        <label>Category
          <select data-filter="category"><option value="">All categories</option>${options('category')}</select>
        </label>
        <label>Agency
          <select data-filter="agency"><option value="">All agencies</option>${options('agency')}</select>
        </label>
      </div>
    </details>`
}).join(''))

const tooltip = $('#tooltip')
const map = createScene($('#map'), jobs, {
  onHover(job, event) {
    tooltip.hidden = !job
    if (!job) return
    tooltip.innerHTML = `<strong>${escapeHtml(job.title)}</strong><br>${escapeHtml(job.career_level)} · ${escapeHtml(job.category)}`
    tooltip.style.left = `${event.clientX + 14}px`
    tooltip.style.top = `${event.clientY + 14}px`
  },
  onSelect: select,
})

let filteredJobs = jobs
let selectedJob = null
let resumeMatches = []
let resumeOnly = true

$('#search').addEventListener('change', (event) => {
  const job = filteredJobs.find((j) => j.title === event.target.value)
  if (job) select(job)
})

$('#clear').addEventListener('click', () => select(null))

$('#resume-file').addEventListener('change', handleResumeUpload)
$('#resume-only').addEventListener('change', (event) => {
  resumeOnly = event.target.checked
  updateFilters()
})
$('#clear-resume').addEventListener('click', clearResume)

layerFilters.querySelectorAll('[data-filter]').forEach((control) => {
  control.addEventListener('input', updateFilters)
  control.addEventListener('change', updateFilters)
})

updateFilters()

function updateFilters() {
  for (const section of layerFilters.querySelectorAll('.layer-filter')) {
    const rank = Number(section.dataset.rank)
    const state = filtersByRank.get(rank)
    section.querySelectorAll('[data-filter]').forEach((control) => {
      state[control.dataset.filter] = control.value
    })
  }

  filteredJobs = jobs.filter((job) => {
    const filter = filtersByRank.get(job.seniority_rank)
    if (!filter) return true
    const minSalary = filter.minSalary === '' ? null : Number(filter.minSalary)
    const maxSalary = filter.maxSalary === '' ? null : Number(filter.maxSalary)
    if (minSalary !== null && (!job.salary_to || job.salary_to < minSalary)) return false
    if (maxSalary !== null && (!job.salary_from || job.salary_from > maxSalary)) return false
    if (filter.location && job.location !== filter.location) return false
    if (filter.category && job.category !== filter.category) return false
    if (filter.agency && job.agency !== filter.agency) return false
    return true
  })

  if (resumeMatches.length && resumeOnly) {
    const topResumeJobIds = new Set(resumeMatches.slice(0, 20).map(({ job }) => job.id))
    filteredJobs = filteredJobs.filter((job) => topResumeJobIds.has(job.id))
  }

  const visibleByRank = new Map()
  for (const job of filteredJobs) {
    visibleByRank.set(job.seniority_rank, (visibleByRank.get(job.seniority_rank) || 0) + 1)
  }
  for (const [rank] of filtersByRank) {
    const count = visibleByRank.get(rank) || 0
    layerFilters.querySelector(`[data-count="${rank}"]`).textContent = `${count.toLocaleString()}`
    layerFilters.querySelector(`[data-rank="${rank}"]`).classList.toggle('empty', count === 0)
  }

  $('#job-count').textContent = `${filteredJobs.length.toLocaleString()} of ${jobs.length.toLocaleString()} postings`
  $('#titles').innerHTML = [...new Set(filteredJobs.map((job) => job.title))]
    .sort()
    .map((title) => `<option value="${escapeHtml(title)}"></option>`)
    .join('')
  map.setVisibleJobs(filteredJobs)
  tooltip.hidden = true
  updateResumeRecommendations()

  if (selectedJob && !filteredJobs.includes(selectedJob)) {
    select(null)
  } else if (selectedJob) {
    select(selectedJob, false)
  }
}

async function handleResumeUpload(event) {
  const [file] = event.target.files
  if (!file) return
  event.target.value = ''

  const status = $('#resume-status')
  status.textContent = 'Reading resume locally…'
  $('#resume-matches').replaceChildren()
  $('#resume-only-option').hidden = true
  $('#clear-resume').hidden = true
  $('#resume-only').checked = true
  resumeOnly = true
  resumeMatches = []
  updateFilters()

  try {
    const text = await readResume(file)
    resumeMatches = matchResumeToJobs(text, jobs)
    if (!resumeMatches.length) {
      throw new Error('No relevant keywords matched the job postings. Try a text-based PDF or a resume with more skills and experience details.')
    }
    const experienceYears = resumeMatches[0].experienceYears
    status.textContent = experienceYears === null
      ? `Found ${resumeMatches.length} keyword-matched postings. Experience years weren't detected.`
      : `Found ${resumeMatches.length} keyword-matched postings. Detected ${experienceYears} years of experience.`
    $('#resume-only-option').hidden = false
    $('#clear-resume').hidden = false
    updateFilters()
  } catch (error) {
    resumeMatches = []
    status.textContent = error instanceof Error ? error.message : 'Could not read this resume.'
    updateFilters()
  }
}

function clearResume() {
  $('#resume-file').value = ''
  $('#resume-status').textContent = ''
  $('#resume-matches').replaceChildren()
  $('#resume-only-option').hidden = true
  $('#clear-resume').hidden = true
  $('#resume-only').checked = true
  resumeMatches = []
  resumeOnly = true
  updateFilters()
}

function updateResumeRecommendations() {
  const list = $('#resume-matches')
  list.replaceChildren()
  if (!resumeMatches.length) return

  const available = new Set(filteredJobs.map((job) => job.id))
  const recommendations = resumeMatches
    .filter(({ job }) => available.has(job.id))
    .slice(0, 5)
  for (const match of recommendations) {
    const item = document.createElement('li')
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'resume-match'
    const title = document.createElement('span')
    title.className = 'resume-match-title'
    title.textContent = match.job.title
    const keywords = document.createElement('span')
    keywords.className = 'resume-match-meta'
    keywords.textContent = `Matched keywords: ${match.matchedTerms.join(', ')}`
    button.append(title, keywords)
    button.addEventListener('click', () => select(match.job))
    item.append(button)
    list.append(item)
  }

  if (!recommendations.length) {
    const item = document.createElement('li')
    item.className = 'muted hint'
    item.textContent = 'No resume matches remain with the current filters.'
    list.append(item)
  }
}

function select(job, focus = true) {
  selectedJob = job
  const path = job ? careerPath(filteredJobs, job) : []
  map.showPath(path, focus)
  $('#job-details').hidden = !job
  $('#path-panel').hidden = !job
  if (!job) {
    $('#search').value = ''
    return
  }
  $('#search').value = job.title
  $('#detail-title').textContent = job.title
  $('#detail-fields').innerHTML = [
    ['Salary', formatSalaryValue(job)],
    ['Location', job.location],
    ['Agency', job.agency],
    ['Category', job.category],
    ['Career level', job.career_level],
    ['Job ID', job.id],
  ]
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value || 'Not listed')}</dd></div>`)
    .join('')
  $('#path').innerHTML = path
    .map(
      (step, i) => `
      <li>
        <button data-index="${i}">
          <span class="swatch" style="background:${SENIORITY_COLORS[step.seniority_rank]}"></span>
          <span>
            <span class="step-title">${escapeHtml(step.title)}</span>
            <span class="step-meta">${escapeHtml(step.career_level)} · ${escapeHtml(step.agency ?? '')}${formatSalary(step)}</span>
          </span>
        </button>
      </li>`,
    )
    .join('')
  $('#path').querySelectorAll('button').forEach((button) => {
    button.addEventListener('click', () => select(path[Number(button.dataset.index)]))
  })
}

function formatSalary(job) {
  const salary = formatSalaryValue(job)
  return salary === 'Not listed' ? '' : ` · ${salary}`
}

function formatSalaryValue(job) {
  if (job.salary_from == null && job.salary_to == null) return 'Not listed'
  const fmt = (n) => `$${Math.round(n).toLocaleString()}`
  const range = job.salary_from != null && job.salary_to != null && job.salary_to !== job.salary_from
    ? `${fmt(job.salary_from)}–${fmt(job.salary_to)}`
    : fmt(job.salary_from ?? job.salary_to)
  const frequency = job.salary_frequency === 'Annual'
    ? '/yr'
    : job.salary_frequency
      ? ` ${job.salary_frequency.toLowerCase()}`
      : ''
  return `${range}${frequency}`
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
}
