import './style.css'
import { createScene, SENIORITY_COLORS } from './scene.js'
import { careerPath, SENIORITY_LABELS } from './paths.js'
import {
  EDUCATION_LEVELS,
  EMPTY_PROFILE,
  educationRequirementLabel,
  experienceRequirementLabel,
  hasQualifications,
  loadProfile,
  readiness,
  saveProfile,
} from './profile.js'
import { openWizard } from './wizard.js'
import { compactMoney, escapeHtml, salaryRange } from './format.js'

const $ = (selector) => document.querySelector(selector)

const { jobs, placeholder } = await fetch(`${import.meta.env.BASE_URL}data/jobs.json`).then((r) => r.json())
const jobById = new Map(jobs.map((job) => [job.id, job]))
const categories = [...new Set(jobs.flatMap((job) => job.categories))].sort()

const state = {
  profile: { ...EMPTY_PROFILE },
  filters: { categories: new Set(), minSalary: 0, qualifiedOnly: false, hideLicense: false },
  selected: null,
  direction: 'forward', // 'forward' = where it leads, 'backward' = how to get there
}

$('#placeholder-note').hidden = !placeholder
$('#legend').innerHTML = SENIORITY_LABELS.map(
  (label, rank) => `<li><span class="swatch" style="background:${SENIORITY_COLORS[rank]};color:${SENIORITY_COLORS[rank]}"></span>${label}</li>`,
).join('')
const titles = [...new Set(jobs.map((job) => job.title))].sort()
$('#titles').innerHTML = titles.map((t) => `<option value="${escapeHtml(t)}"></option>`).join('')

const tooltip = $('#tooltip')
const map = createScene($('#map'), jobs, {
  onHover(job, event) {
    tooltip.hidden = !job
    if (!job) return
    tooltip.innerHTML = `<strong>${escapeHtml(job.title)}</strong><br>${escapeHtml(job.career_level)} · ${salaryRange(job)}`
    tooltip.style.left = `${event.clientX + 14}px`
    tooltip.style.top = `${event.clientY + 14}px`
  },
  onSelect: (job) => select(job),
  getInsets() {
    const panel = $('#panel').getBoundingClientRect()
    const docked = panel.top > window.innerHeight * 0.3 // bottom sheet on narrow screens
    return docked ? { left: 0, bottom: window.innerHeight - panel.top } : { left: panel.right, bottom: 0 }
  },
})
new ResizeObserver(() => map.resize()).observe($('#panel'))

// --- Filters ----------------------------------------------------------------

/**
 * Whether `job` passes the current filters. The "qualify now" filter is
 * about where to start, so paths ignore it when choosing later steps.
 */
function passesFilters(job, { forPath = false } = {}) {
  const { filters, profile } = state
  if (filters.categories.size && !job.categories.some((c) => filters.categories.has(c))) return false
  const topPay = job.salary_to ?? job.salary_mid
  if (filters.minSalary && topPay != null && topPay < filters.minSalary) return false
  if (filters.hideLicense && job.license) return false
  if (!forPath && filters.qualifiedOnly && !readiness(profile, job).confirmed) return false
  return true
}

function renderFilters() {
  const { filters, profile } = state
  $('#industries').innerHTML = categories
    .map(
      (category) =>
        `<button class="chip ${filters.categories.has(category) ? 'selected' : ''}" data-value="${escapeHtml(category)}">${escapeHtml(category)}</button>`,
    )
    .join('')
  $('#min-salary').value = filters.minSalary
  $('#min-salary-value').textContent = filters.minSalary ? `${compactMoney(filters.minSalary)}+` : 'Any'
  $('#qualified-only').checked = filters.qualifiedOnly
  $('#qualified-only').disabled = !hasQualifications(profile)
  $('#qualified-only-hint').hidden = hasQualifications(profile)
  $('#hide-license').checked = filters.hideLicense
}

$('#industries').addEventListener('click', (event) => {
  const chip = event.target.closest('.chip')
  if (!chip) return
  const { categories: selected } = state.filters
  if (selected.has(chip.dataset.value)) selected.delete(chip.dataset.value)
  else selected.add(chip.dataset.value)
  refresh()
})
$('#clear-industries').addEventListener('click', () => {
  state.filters.categories.clear()
  refresh()
})
$('#min-salary').addEventListener('input', (event) => {
  state.filters.minSalary = Number(event.target.value)
  refresh()
})
$('#qualified-only').addEventListener('change', (event) => {
  state.filters.qualifiedOnly = event.target.checked
  refresh()
})
$('#hide-license').addEventListener('change', (event) => {
  state.filters.hideLicense = event.target.checked
  refresh()
})

// --- Profile ----------------------------------------------------------------

function applyProfile(profile) {
  state.profile = profile
  state.filters.categories = new Set(profile.fields)
  state.filters.minSalary = profile.minSalary
  state.filters.qualifiedOnly = false
  state.direction = profile.goal === 'target' ? 'backward' : 'forward'
  state.selected = jobById.get(profile.anchorId) ?? null
  saveProfile(profile)
  refresh()
}

function renderProfileSummary() {
  const { profile } = state
  const parts = []
  if (profile.education != null) parts.push(EDUCATION_LEVELS[profile.education])
  if (profile.years != null) parts.push(profile.years === 0 ? 'No experience yet' : `${profile.years}+ yrs experience`)
  if (profile.minSalary) parts.push(`${compactMoney(profile.minSalary)}+ salary`)
  $('#profile-summary').textContent = parts.length ? parts.join(' · ') : 'Answer a few questions to personalize the map.'
  $('#edit-profile').textContent = profile.goal ? 'Edit answers' : 'Get started'
}

function startWizard() {
  openWizard({ jobs, categories, initial: state.profile, onDone: applyProfile })
}
$('#edit-profile').addEventListener('click', startWizard)

// --- Selection & results ----------------------------------------------------

function select(job, direction = state.direction) {
  state.selected = job
  state.direction = direction
  refresh()
}

$('#search').addEventListener('change', (event) => {
  const job = jobs.find((j) => j.title === event.target.value)
  if (job) select(job)
})

function readinessBadge(job) {
  if (!hasQualifications(state.profile)) return ''
  const { confirmed, missing } = readiness(state.profile, job)
  if (confirmed) return '<span class="badge ok">You meet the listed minimums</span>'
  if (!missing.length) return '<span class="badge unknown">Check the posting for requirements</span>'
  return missing.map((m) => `<span class="badge gap">${escapeHtml(m)}</span>`).join('')
}

function jobCard(job, { index, label } = {}) {
  return `
    <button class="job-card" data-id="${job.id}" ${index != null ? `data-index="${index}"` : ''}>
      <span class="swatch" style="background:${SENIORITY_COLORS[job.seniority_rank]};color:${SENIORITY_COLORS[job.seniority_rank]}"></span>
      <span class="job-card-body">
        ${label ? `<span class="step-label">${escapeHtml(label)}</span>` : ''}
        <span class="step-title">${escapeHtml(job.title)}</span>
        <span class="step-meta">${escapeHtml(job.career_level)} · ${escapeHtml(job.agency)}</span>
        <span class="facts">
          <span>${salaryRange(job)}</span>
          <span>${educationRequirementLabel(job.min_education_rank)}</span>
          <span>${experienceRequirementLabel(job.min_years_experience)}</span>
          ${job.license ? '<span>License / certification</span>' : ''}
        </span>
        <span class="badges">${readinessBadge(job)}</span>
      </span>
    </button>`
}

function renderPath(path) {
  const anchor = state.selected
  const backward = state.direction === 'backward'
  // On a "how to get there" path, point out the most senior step the student can already apply to.
  let startIndex = -1
  if (backward && hasQualifications(state.profile)) {
    path.forEach((job, i) => {
      if (readiness(state.profile, job).confirmed) startIndex = i
    })
  }

  $('#results').innerHTML = `
    <div class="section-head">
      <h2>${backward ? 'How to get there' : 'Where it can lead'}</h2>
      <button id="clear" class="link">Clear</button>
    </div>
    <div class="segmented" role="group" aria-label="Path direction">
      <button data-direction="forward" aria-pressed="${!backward}">Where it leads</button>
      <button data-direction="backward" aria-pressed="${backward}">How to get here</button>
    </div>
    ${path.length === 1 ? `<p class="muted">No ${backward ? 'more junior' : 'more senior'} jobs match your filters. Try loosening them.</p>` : ''}
    <ol class="path">
      ${path
        .map((job, i) => {
          let label = ''
          if (job === anchor) label = backward ? 'Your goal' : 'Starting point'
          else if (i === startIndex) label = 'You could start here'
          return `<li>${jobCard(job, { index: i, label })}</li>`
        })
        .join('')}
    </ol>`

  $('#clear').addEventListener('click', () => select(null))
  $('#results').querySelectorAll('[data-direction]').forEach((button) =>
    button.addEventListener('click', () => select(anchor, button.dataset.direction)),
  )
  $('#results').querySelectorAll('.job-card').forEach((card) =>
    card.addEventListener('click', () => select(path[Number(card.dataset.index)])),
  )
}

/** Entry-level jobs the student can apply to now, best paid first. */
function startingSuggestions() {
  const candidates = jobs.filter((job) => passesFilters(job) && readiness(state.profile, job).confirmed)
  for (const maxRank of [1, 2]) {
    const picks = candidates
      .filter((job) => job.seniority_rank <= maxRank)
      .sort((a, b) => (b.salary_mid ?? 0) - (a.salary_mid ?? 0))
    const seen = new Set()
    const unique = picks.filter((job) => !seen.has(job.title) && seen.add(job.title))
    if (unique.length) return unique.slice(0, 5)
  }
  return []
}

function renderSuggestions() {
  const suggestions = startingSuggestions()
  const personalized = hasQualifications(state.profile)
  $('#results').innerHTML = `
    <h2>${personalized ? 'Good places to start' : 'Highest-paying entry-level jobs'}</h2>
    <p class="muted hint">${
      personalized
        ? 'Entry-level jobs you meet the listed minimums for. Pick one to see where it leads.'
        : 'Pick one to see where it leads, or answer a few questions to personalize this list.'
    }</p>
    ${
      suggestions.length
        ? `<ol class="path">${suggestions.map((job) => `<li>${jobCard(job)}</li>`).join('')}</ol>`
        : '<p class="muted">Nothing matches yet. Try loosening the filters below.</p>'
    }`
  $('#results').querySelectorAll('.job-card').forEach((card) =>
    card.addEventListener('click', () => select(jobById.get(card.dataset.id), 'forward')),
  )
}

// --- Refresh ----------------------------------------------------------------

function refresh() {
  const visibleCount = jobs.filter((job) => passesFilters(job)).length
  map.setFilter((job) => passesFilters(job))
  $('#job-count').textContent =
    visibleCount === jobs.length
      ? `${jobs.length.toLocaleString()} NYC job postings`
      : `Showing ${visibleCount.toLocaleString()} of ${jobs.length.toLocaleString()} NYC job postings`

  if (state.selected) {
    const candidates = jobs.filter((job) => passesFilters(job, { forPath: true }))
    const path = careerPath(candidates.includes(state.selected) ? candidates : [...candidates, state.selected], state.selected, state.direction, {
      sameField: placeholder,
    })
    map.showPath(path)
    renderPath(path)
    $('#search').value = state.selected.title
  } else {
    map.showPath([])
    renderSuggestions()
    $('#search').value = ''
  }
  renderFilters()
  renderProfileSummary()
}

const saved = loadProfile()
if (saved) applyProfile(saved)
else {
  refresh()
  startWizard()
}
