// Step-by-step onboarding that turns a few questions into a starting view:
// which mode to use, which job to anchor on, and the student's qualifications.

import { EDUCATION_LEVELS, EMPTY_PROFILE } from './profile.js'
import { compactMoney, escapeHtml, median } from './format.js'

const GOALS = [
  {
    value: 'explore',
    label: "I'm exploring",
    detail: "I'm not sure what I want yet and want to see what's out there.",
  },
  {
    value: 'target',
    label: 'I have a job in mind',
    detail: 'Show me the steps that lead to it.',
  },
  {
    value: 'current',
    label: 'I want to grow from where I am',
    detail: 'Start from my current or most recent job and show where it can lead.',
  },
]

const EXPERIENCE = [
  { value: 0, label: 'None yet' },
  { value: 1, label: 'About 1 year' },
  { value: 2, label: '2–3 years' },
  { value: 4, label: '4–5 years' },
  { value: 6, label: '6+ years' },
]

const SALARIES = [0, 40000, 60000, 80000, 100000]

/**
 * Opens the wizard over the page.
 *
 * @param {object} options
 * @param {object[]} options.jobs
 * @param {string[]} options.categories
 * @param {object} [options.initial] previous answers to start from
 * @param {(profile: object) => void} options.onDone
 */
export function openWizard({ jobs, categories, initial, onDone }) {
  const draft = { ...EMPTY_PROFILE, ...initial, fields: [...(initial?.fields ?? [])] }
  const entryMedian = median(jobs.filter((j) => j.seniority_rank === 1).map((j) => j.salary_mid))
  const jobById = new Map(jobs.map((job) => [job.id, job]))

  const root = document.createElement('div')
  root.className = 'wizard-backdrop'
  root.innerHTML = `
    <div class="wizard" role="dialog" aria-modal="true" aria-labelledby="wizard-title">
      <div class="wizard-progress"><div class="wizard-progress-bar"></div></div>
      <p class="wizard-step-count"></p>
      <h2 id="wizard-title"></h2>
      <p class="wizard-why"></p>
      <div class="wizard-body"></div>
      <div class="wizard-actions">
        <button class="link" data-action="skip-all">Skip to the map</button>
        <span class="spacer"></span>
        <button class="secondary" data-action="back">Back</button>
        <button class="primary" data-action="next">Next</button>
      </div>
    </div>`
  document.body.appendChild(root)

  const $ = (selector) => root.querySelector(selector)
  let index = 0

  function steps() {
    const list = [goalStep]
    if (draft.goal === 'target' || draft.goal === 'current') list.push(anchorStep)
    // Before a goal is picked, count the fields step so the total doesn't jump.
    else list.push(fieldsStep)
    list.push(educationStep, experienceStep, salaryStep)
    return list
  }

  // --- Steps -------------------------------------------------------------

  const goalStep = {
    title: 'What brings you here?',
    why: "We'll set up the map around what you're trying to figure out.",
    isComplete: () => draft.goal != null,
    render(body) {
      body.innerHTML = choiceList(
        GOALS.map((g) => ({ ...g, selected: draft.goal === g.value })),
      )
      bindChoices(body, (value) => {
        if (draft.goal !== value) draft.anchorId = null
        draft.goal = value
      })
    },
  }

  const anchorStep = {
    get title() {
      return draft.goal === 'target' ? 'Which job are you aiming for?' : "What's your current or most recent job?"
    },
    get why() {
      return draft.goal === 'target'
        ? "We'll work backward from it to show jobs that can lead there."
        : "We'll find similar jobs and show where they lead. Pick the closest match."
    },
    isComplete: () => draft.anchorId != null,
    optional: true,
    render(body) {
      const chosen = jobById.get(draft.anchorId)
      body.innerHTML = `
        <input class="wizard-search" type="search" placeholder="Try “analyst”, “nurse”, “engineer”…" autocomplete="off"
               value="${escapeHtml(chosen?.title ?? '')}" />
        <ul class="wizard-results"></ul>`
      const input = body.querySelector('input')
      const results = body.querySelector('ul')

      const renderResults = () => {
        const query = input.value.trim().toLowerCase()
        const seen = new Set()
        const matches = jobs
          .filter((job) => query && job.title.toLowerCase().includes(query))
          .filter((job) => !seen.has(job.title) && seen.add(job.title))
          .slice(0, 6)
        results.innerHTML = matches
          .map(
            (job) => `
            <li><button class="result ${job.id === draft.anchorId ? 'selected' : ''}" data-id="${job.id}">
              <span class="result-title">${escapeHtml(job.title)}</span>
              <span class="result-meta">${escapeHtml(job.career_level)} · ${escapeHtml(job.agency)}</span>
            </button></li>`,
          )
          .join('')
        if (query && !matches.length) results.innerHTML = '<li class="muted">No matches. Try a shorter word.</li>'
        results.querySelectorAll('button').forEach((button) =>
          button.addEventListener('click', () => {
            draft.anchorId = button.dataset.id
            input.value = jobById.get(draft.anchorId).title
            renderResults()
            update()
          }),
        )
      }
      input.addEventListener('input', () => {
        draft.anchorId = null
        renderResults()
        update()
      })
      renderResults()
      setTimeout(() => input.focus())
    },
  }

  const fieldsStep = {
    title: 'Which fields sound interesting?',
    why: 'Pick as many as you like. Leave them all off to see everything.',
    isComplete: () => true,
    render(body) {
      body.innerHTML = `<div class="chips">${categories
        .map(
          (category) =>
            `<button class="chip ${draft.fields.includes(category) ? 'selected' : ''}" data-value="${escapeHtml(category)}">${escapeHtml(category)}</button>`,
        )
        .join('')}</div>`
      body.querySelectorAll('.chip').forEach((chip) =>
        chip.addEventListener('click', () => {
          const value = chip.dataset.value
          draft.fields = draft.fields.includes(value)
            ? draft.fields.filter((f) => f !== value)
            : [...draft.fields, value]
          chip.classList.toggle('selected')
        }),
      )
    },
  }

  const educationStep = {
    title: "What's the highest education you have, or will have soon?",
    why: "We'll mark which jobs you already meet the education requirement for.",
    isComplete: () => draft.education != null,
    optional: true,
    render(body) {
      body.innerHTML = choiceList(
        EDUCATION_LEVELS.map((label, value) => ({ value, label, selected: draft.education === value })),
        true,
      )
      bindChoices(body, (value) => (draft.education = Number(value)))
    },
  }

  const experienceStep = {
    title: 'How much full-time work experience do you have?',
    why: 'Internships and part-time work count toward some NYC jobs, but most list full-time years.',
    isComplete: () => draft.years != null,
    optional: true,
    render(body) {
      body.innerHTML = choiceList(
        EXPERIENCE.map((e) => ({ ...e, selected: draft.years === e.value })),
        true,
      )
      bindChoices(body, (value) => (draft.years = Number(value)))
    },
  }

  const salaryStep = {
    title: "What's the lowest yearly salary that would work for you?",
    get why() {
      return entryMedian
        ? `For reference, entry-level jobs here pay a median of ${compactMoney(entryMedian)} a year.`
        : ''
    },
    isComplete: () => true,
    render(body) {
      body.innerHTML = choiceList(
        SALARIES.map((value) => ({
          value,
          label: value ? `${compactMoney(value)}+` : 'No minimum',
          selected: draft.minSalary === value,
        })),
        true,
      )
      bindChoices(body, (value) => (draft.minSalary = Number(value)))
    },
  }

  // --- Rendering -----------------------------------------------------------

  function choiceList(options, compact = false) {
    return `<div class="choices ${compact ? 'compact' : ''}">${options
      .map(
        (o) => `
        <button class="choice ${o.selected ? 'selected' : ''}" data-value="${escapeHtml(o.value)}" aria-pressed="${o.selected}">
          <span class="choice-label">${escapeHtml(o.label)}</span>
          ${o.detail ? `<span class="choice-detail">${escapeHtml(o.detail)}</span>` : ''}
        </button>`,
      )
      .join('')}</div>`
  }

  function bindChoices(body, onPick) {
    body.querySelectorAll('.choice').forEach((button) =>
      button.addEventListener('click', () => {
        onPick(button.dataset.value)
        body.querySelectorAll('.choice').forEach((b) => {
          b.classList.toggle('selected', b === button)
          b.setAttribute('aria-pressed', b === button)
        })
        update()
      }),
    )
  }

  function render() {
    const list = steps()
    const step = list[index]
    $('.wizard-step-count').textContent = `Step ${index + 1} of ${list.length}`
    $('.wizard-progress-bar').style.width = `${((index + 1) / list.length) * 100}%`
    $('#wizard-title').textContent = step.title
    $('.wizard-why').textContent = step.why
    step.render($('.wizard-body'))
    update()
  }

  /** Refresh the buttons without re-rendering the step (keeps input focus). */
  function update() {
    const list = steps()
    const step = list[index]
    const isLast = index === list.length - 1
    $('[data-action="back"]').hidden = index === 0
    const next = $('[data-action="next"]')
    if (step.optional && !step.isComplete()) {
      next.textContent = 'Skip'
      next.className = 'secondary'
      next.disabled = false
    } else {
      next.textContent = isLast ? 'Show my map' : 'Next'
      next.className = 'primary'
      next.disabled = !step.isComplete()
    }
  }

  function finish(profile) {
    root.remove()
    document.removeEventListener('keydown', onKey)
    onDone(profile)
  }

  function onKey(event) {
    if (event.key === 'Escape') finish({ ...draft, goal: draft.goal ?? 'explore' })
  }
  document.addEventListener('keydown', onKey)

  root.addEventListener('click', (event) => {
    const action = event.target.closest('[data-action]')?.dataset.action
    if (action === 'back') {
      index -= 1
      render()
    } else if (action === 'next') {
      if (index === steps().length - 1) finish(draft)
      else {
        index += 1
        render()
      }
    } else if (action === 'skip-all') {
      finish({ ...draft, goal: draft.goal ?? 'explore' })
    }
  })

  render()
}
