// The student's answers from the wizard, and how they compare to a job's
// listed minimum requirements.

export const EDUCATION_LEVELS = [
  'No diploma yet',
  'High school / GED',
  "Associate's",
  "Bachelor's",
  "Master's",
  'Doctorate / professional',
]

// Shorter labels for a job's requirement ("Needs a Bachelor's").
const EDUCATION_REQUIREMENTS = [
  'No education requirement',
  'High school / GED',
  "Associate's degree",
  "Bachelor's degree",
  "Master's degree",
  'Doctorate / professional degree',
]

export function educationRequirementLabel(rank) {
  return rank == null ? 'Education not listed' : EDUCATION_REQUIREMENTS[rank]
}

export function experienceRequirementLabel(years) {
  if (years == null) return 'Experience not listed'
  if (years === 0) return 'No experience required'
  return `${years} yr${years === 1 ? '' : 's'} experience`
}

export const EMPTY_PROFILE = {
  goal: null, // 'explore' | 'target' | 'current'
  anchorId: null, // target job (goal 'target') or current job (goal 'current')
  fields: [],
  education: null,
  years: null,
  minSalary: 0,
}

export function hasQualifications(profile) {
  return profile.education != null || profile.years != null
}

/**
 * What the student is missing for `job`, based on its listed minimums.
 * Unknown requirements or unanswered questions never count as missing, but
 * `unlisted` is set when a requirement the student answered isn't listed, so
 * callers don't claim a match they can't back up.
 */
export function readiness(profile, job) {
  const missing = []
  const unlisted =
    (profile.education != null && job.min_education_rank == null) ||
    (profile.years != null && job.min_years_experience == null)
  if (profile.education != null && job.min_education_rank != null && job.min_education_rank > profile.education) {
    missing.push(`Needs ${EDUCATION_REQUIREMENTS[job.min_education_rank]}`)
  }
  if (profile.years != null && job.min_years_experience != null && job.min_years_experience > profile.years) {
    const gap = job.min_years_experience - profile.years
    missing.push(`Needs ${gap} more yr${gap === 1 ? '' : 's'} experience`)
  }
  const qualifies = missing.length === 0
  return { qualifies, missing, unlisted, confirmed: qualifies && !unlisted }
}

const STORAGE_KEY = 'career-map-profile'

export function loadProfile() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY))
    return saved ? { ...EMPTY_PROFILE, ...saved } : null
  } catch {
    return null
  }
}

export function saveProfile(profile) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
  } catch {
    // Storage can be unavailable (private windows); the wizard just reappears.
  }
}
