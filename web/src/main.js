import './style.css'
import { createScene, SENIORITY_COLORS } from './scene.js'
import { careerPath, SENIORITY_LABELS } from './paths.js'

const $ = (selector) => document.querySelector(selector)

const { jobs, placeholder } = await fetch(`${import.meta.env.BASE_URL}data/jobs.json`).then((r) => r.json())

$('#placeholder-note').hidden = !placeholder
$('#job-count').textContent = `${jobs.length.toLocaleString()} postings`

$('#legend').innerHTML = SENIORITY_LABELS.map(
  (label, rank) =>
    `<li><span class="swatch" style="background:${SENIORITY_COLORS[rank]}"></span>${label}</li>`,
).join('')

const titles = [...new Set(jobs.map((job) => job.title))].sort()
$('#titles').innerHTML = titles.map((t) => `<option value="${escapeHtml(t)}"></option>`).join('')

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

$('#search').addEventListener('change', (event) => {
  const job = jobs.find((j) => j.title === event.target.value)
  if (job) select(job)
})

$('#clear').addEventListener('click', () => select(null))

function select(job) {
  const path = job ? careerPath(jobs, job) : []
  map.showPath(path)
  $('#path-panel').hidden = !job
  if (!job) {
    $('#search').value = ''
    return
  }
  $('#search').value = job.title
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
  if (!job.salary_from) return ''
  const fmt = (n) => `$${Math.round(n).toLocaleString()}`
  const range = job.salary_to && job.salary_to !== job.salary_from
    ? `${fmt(job.salary_from)}–${fmt(job.salary_to)}`
    : fmt(job.salary_from)
  return ` · ${range}${job.salary_frequency === 'Annual' ? '/yr' : ` ${job.salary_frequency?.toLowerCase() ?? ''}`}`
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
}
