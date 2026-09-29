// Career path logic: from a starting job, repeatedly step to the nearest job
// (in the 3D embedding space) that sits at a higher seniority rank.

export const SENIORITY_LABELS = [
  'Student',
  'Entry-Level',
  'Experienced (non-manager)',
  'Manager',
  'Executive',
]

const MAX_RANK = SENIORITY_LABELS.length - 1

function distanceSq(a, b) {
  const dx = a.x - b.x
  const dy = a.y - b.y
  const dz = a.z - b.z
  return dx * dx + dy * dy + dz * dz
}

/** Nearest `k` jobs to `job` at exactly `rank`, closest first. */
export function nearestAtRank(jobs, job, rank, k = 1) {
  return jobs
    .filter((other) => other.seniority_rank === rank && other !== job)
    .map((other) => ({ job: other, d: distanceSq(job, other) }))
    .sort((a, b) => a.d - b.d)
    .slice(0, k)
    .map((entry) => entry.job)
}

/**
 * Greedy path from `start` up to the most senior level. If no job exists at
 * the next rank, skip ahead to the next rank that has one.
 */
export function careerPath(jobs, start) {
  const path = [start]
  let current = start
  for (let rank = start.seniority_rank + 1; rank <= MAX_RANK; rank++) {
    const [next] = nearestAtRank(jobs, current, rank)
    if (!next) continue
    path.push(next)
    current = next
  }
  return path
}
