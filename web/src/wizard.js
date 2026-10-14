// Onboarding played like a character-creation screen: one question at a
// time, chunky tiles that advance on click, and a player card that fills in
// as the student answers. The answers set up the starting map view.

import { EDUCATION_LEVELS, EMPTY_PROFILE } from './profile.js'
import { compactMoney, escapeHtml, median } from './format.js'

const GOALS = [
  { value: 'explore', label: 'Still exploring', detail: 'Browse jobs by field' },
  { value: 'target', label: 'I have a job in mind', detail: 'See how to get there' },
  { value: 'current', label: 'I want to move up', detail: 'See where my current job leads' },
]

const GOAL_LABELS = Object.fromEntries(GOALS.map((g) => [g.value, g.label]))

const EXPERIENCE = [
  { value: 0, label: 'None' },
  { value: 1, label: '1 year' },
  { value: 2, label: '2–3 years' },
  { value: 4, label: '4–5 years' },
  { value: 6, label: '6+ years' },
]

const SALARIES = [0, 40000, 60000, 80000, 100000]

// Pause after a pick so the tile's "pop" is visible before moving on.
const ADVANCE_DELAY = 380

/**
 * Opens the onboarding over the page.
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
  root.className = 'game'
  root.setAttribute('role', 'dialog')
  root.setAttribute('aria-modal', 'true')
  root.setAttribute('aria-labelledby', 'game-title')
  root.innerHTML = `
    <header class="game-top">
      <button class="game-back" data-action="back">← Back</button>
      <ol class="pips" aria-hidden="true"></ol>
      <button class="link" data-action="skip-all">Skip to map</button>
    </header>
    <div class="game-stage">
      <section class="game-question" aria-live="polite"></section>
      <aside class="player-card" aria-label="Your answers"></aside>
    </div>`
  document.body.appendChild(root)

  const $ = (selector) => root.querySelector(selector)
  // First-time visitors see a start screen (index -1) before the questions.
  let index = initial?.goal ? 0 : -1
  let advancing = null

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
    title: 'Where are you in your job search?',
    isComplete: () => draft.goal != null,
    render(body) {
      body.innerHTML = tiles(GOALS.map((g) => ({ ...g, selected: draft.goal === g.value })), 'big')
      bindTiles(body, (value) => {
        if (draft.goal !== value) draft.anchorId = null
        draft.goal = value
      })
    },
  }

  const anchorStep = {
    get title() {
      return draft.goal === 'target' ? 'What job do you want?' : "What's your current job?"
    },
    get hint() {
      return draft.goal === 'target' ? 'Type a few letters and pick one.' : 'Or your most recent one.'
    },
    isComplete: () => draft.anchorId != null,
    optional: true,
    render(body) {
      const chosen = jobById.get(draft.anchorId)
      body.innerHTML = `
        <input class="game-search" type="search" placeholder="analyst, nurse, engineer…" autocomplete="off"
               aria-label="Search job titles" value="${escapeHtml(chosen?.title ?? '')}" />
        <ul class="game-results"></ul>`
      const input = body.querySelector('input')
      const results = body.querySelector('ul')

      const renderResults = () => {
        const query = input.value.trim().toLowerCase()
        const seen = new Set()
        const matches = jobs
          .filter((job) => query && job.title.toLowerCase().includes(query))
          .filter((job) => !seen.has(job.title) && seen.add(job.title))
          .slice(0, 5)
        results.innerHTML = matches
          .map(
            (job) => `
            <li><button class="result ${job.id === draft.anchorId ? 'selected' : ''}" data-id="${job.id}">
              <span class="result-title">${escapeHtml(job.title)}</span>
              <span class="result-meta">${escapeHtml(job.career_level)} · ${escapeHtml(job.agency)}</span>
            </button></li>`,
          )
          .join('')
        if (query && !matches.length) results.innerHTML = '<li class="muted">No matches.</li>'
        results.querySelectorAll('button').forEach((button) =>
          button.addEventListener('click', () => {
            draft.anchorId = button.dataset.id
            input.value = jobById.get(draft.anchorId).title
            button.classList.add('selected', 'pop')
            renderCard()
            advanceSoon()
          }),
        )
      }
      input.addEventListener('input', () => {
        draft.anchorId = null
        renderResults()
        renderCard()
      })
      renderResults()
      setTimeout(() => input.focus())
    },
  }

  const fieldsStep = {
    title: 'What fields are you interested in?',
    hint: 'Pick as many as you want.',
    multi: true,
    isComplete: () => true,
    render(body) {
      body.innerHTML = `<div class="field-cloud">${categories
        .map(
          (category, i) =>
            `<button class="field ${draft.fields.includes(category) ? 'selected' : ''}" style="--tilt:${tilt(i)}" data-value="${escapeHtml(category)}">${escapeHtml(category)}</button>`,
        )
        .join('')}</div>`
      body.querySelectorAll('.field').forEach((chip) =>
        chip.addEventListener('click', () => {
          const value = chip.dataset.value
          draft.fields = draft.fields.includes(value)
            ? draft.fields.filter((f) => f !== value)
            : [...draft.fields, value]
          chip.classList.toggle('selected')
          chip.classList.remove('pop')
          void chip.offsetWidth // restart the pop animation
          chip.classList.add('pop')
          renderCard()
          renderActions()
        }),
      )
    },
  }

  const educationStep = {
    title: "What's your highest level of education?",
    hint: "Count a degree you'll finish soon.",
    isComplete: () => draft.education != null,
    optional: true,
    render(body) {
      body.innerHTML = tiles(
        EDUCATION_LEVELS.map((label, value) => ({ value, label, selected: draft.education === value })),
      )
      bindTiles(body, (value) => (draft.education = Number(value)))
    },
  }

  const experienceStep = {
    title: 'How many years of full-time work experience do you have?',
    isComplete: () => draft.years != null,
    optional: true,
    render(body) {
      body.innerHTML = tiles(EXPERIENCE.map((e) => ({ ...e, selected: draft.years === e.value })))
      bindTiles(body, (value) => (draft.years = Number(value)))
    },
  }

  const salaryStep = {
    title: "What's the lowest salary you'd accept?",
    get hint() {
      return entryMedian ? `Entry-level jobs here pay about ${compactMoney(entryMedian)} a year.` : ''
    },
    isComplete: () => true,
    render(body) {
      body.innerHTML = tiles(
        SALARIES.map((value) => ({
          value,
          label: value ? `${compactMoney(value)}+` : 'No minimum',
          selected: draft.minSalary === value,
        })),
      )
      bindTiles(body, (value) => (draft.minSalary = Number(value)))
    },
  }

  // --- Pieces --------------------------------------------------------------

  /** Small alternating rotation so tiles look hand-placed rather than gridded. */
  function tilt(i) {
    return `${[-1.6, 1.2, -0.6, 1.8, -1.2, 0.8][i % 6]}deg`
  }

  function tiles(options, size = '') {
    return `<div class="tiles ${size}">${options
      .map(
        (o, i) => `
        <button class="tile ${o.selected ? 'selected' : ''}" style="--tilt:${tilt(i)}" data-value="${escapeHtml(o.value)}" aria-pressed="${o.selected}">
          <span class="tile-key" aria-hidden="true">${i + 1}</span>
          <span class="tile-label">${escapeHtml(o.label)}</span>
          ${o.detail ? `<span class="tile-detail">${escapeHtml(o.detail)}</span>` : ''}
        </button>`,
      )
      .join('')}</div>`
  }

  function bindTiles(body, onPick) {
    body.querySelectorAll('.tile').forEach((button) =>
      button.addEventListener('click', () => {
        if (advancing) return
        onPick(button.dataset.value)
        body.querySelectorAll('.tile').forEach((b) => {
          b.classList.toggle('selected', b === button)
          b.setAttribute('aria-pressed', b === button)
        })
        button.classList.add('pop')
        renderCard()
        advanceSoon()
      }),
    )
  }

  function renderPips() {
    const list = steps()
    $('.pips').innerHTML = list
      .map((_, i) => `<li class="${i < index ? 'done' : i === index ? 'current' : ''}"></li>`)
      .join('')
  }

  /** The player card: every answer so far, filling in as the student plays. */
  function renderCard() {
    const anchor = jobById.get(draft.anchorId)
    const onLastStep = index >= steps().length - 1
    const rows = [
      ['Goal', GOAL_LABELS[draft.goal]],
      draft.goal === 'target' || draft.goal === 'current'
        ? [draft.goal === 'target' ? 'Dream job' : 'Current job', anchor?.title]
        : ['Fields', draft.fields.length ? `${draft.fields.length} picked` : null],
      ['Education', draft.education != null ? EDUCATION_LEVELS[draft.education] : null],
      ['Experience', draft.years != null ? EXPERIENCE.find((e) => e.value === draft.years)?.label : null],
      ['Salary', draft.minSalary ? `${compactMoney(draft.minSalary)}+` : onLastStep ? 'Any' : null],
    ]
    const card = $('.player-card')
    const previous = new Map([...card.querySelectorAll('.stat')].map((el) => [el.dataset.key, el.dataset.value]))
    card.innerHTML = `
      <p class="card-title">Your card</p>
      <dl>${rows
        .map(([key, value]) => {
          const isNew = value && previous.has(key) && previous.get(key) !== String(value)
          return `<div class="stat ${value ? 'filled' : ''} ${isNew ? 'pop' : ''}" data-key="${key}" data-value="${escapeHtml(value ?? '')}">
            <dt>${key}</dt><dd>${value ? escapeHtml(value) : '?'}</dd>
          </div>`
        })
        .join('')}</dl>`
  }

  /** Buttons under the question: only for steps that don't advance on a click. */
  function renderActions() {
    const step = steps()[index]
    const actions = $('.game-actions')
    if (!actions) return
    if (step.multi) {
      actions.innerHTML = `<button class="primary" data-action="next">${draft.fields.length ? 'Done' : 'Skip, show all fields'}</button>`
    } else if (step.optional) {
      actions.innerHTML = '<button class="link" data-action="next">Skip this one</button>'
    } else {
      actions.innerHTML = ''
    }
  }

  // --- Rendering -------------------------------------------------------------

  function renderStart() {
    root.classList.add('start')
    $('.game-question').innerHTML = `
      <p class="game-level">NYC Career Paths</p>
      <h2 id="game-title" class="start-title">See where a job can take you</h2>
      <p class="game-hint">${jobs.length.toLocaleString()} NYC government jobs, from entry level to executive.
        Answer 5 questions and we'll map paths that fit you.</p>
      <div class="game-actions"><button class="primary big" data-action="next">Start</button></div>
      <p class="press-key">or press Enter</p>`
    $('.player-card').hidden = true
    $('.pips').innerHTML = ''
    $('.game-back').hidden = true
  }

  function render() {
    advancing = null
    if (index < 0) return renderStart()
    root.classList.remove('start')
    $('.player-card').hidden = false
    $('.game-back').hidden = index === 0
    const step = steps()[index]
    $('.game-question').innerHTML = `
      <div class="game-step">
        <p class="game-level">Question ${index + 1}</p>
        <h2 id="game-title">${escapeHtml(step.title)}</h2>
        ${step.hint ? `<p class="game-hint">${escapeHtml(step.hint)}</p>` : ''}
        <div class="game-body"></div>
        <div class="game-actions"></div>
      </div>`
    step.render($('.game-body'))
    renderActions()
    renderPips()
    renderCard()
  }

  function goNext() {
    if (index >= 0 && index === steps().length - 1) finish(draft)
    else {
      index += 1
      render()
    }
  }

  function advanceSoon() {
    clearTimeout(advancing)
    advancing = setTimeout(goNext, ADVANCE_DELAY)
  }

  function finish(profile) {
    clearTimeout(advancing)
    root.remove()
    document.removeEventListener('keydown', onKey)
    onDone(profile)
  }

  function onKey(event) {
    if (event.key === 'Escape') return finish({ ...draft, goal: draft.goal ?? 'explore' })
    if (index < 0 && event.key === 'Enter') return goNext()
    // Number keys pick tiles, unless the student is typing in the search box.
    if (event.target.matches?.('input')) return
    const tile = root.querySelectorAll('.tile')[Number(event.key) - 1]
    if (tile) tile.click()
  }
  document.addEventListener('keydown', onKey)

  root.addEventListener('click', (event) => {
    const action = event.target.closest('[data-action]')?.dataset.action
    if (action === 'back') {
      clearTimeout(advancing)
      index -= 1
      render()
    } else if (action === 'next') {
      goNext()
    } else if (action === 'skip-all') {
      finish({ ...draft, goal: draft.goal ?? 'explore' })
    }
  })

  render()
}
