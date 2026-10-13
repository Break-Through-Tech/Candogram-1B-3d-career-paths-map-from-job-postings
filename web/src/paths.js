// Career path logic: step between seniority levels by moving to the nearest
// job (in the 3D embedding space) at the next level up or down.

export const SENIORITY_LABELS = [
  'Student',
  'Entry-Level',
  'Experienced (non-manager)',
  'Manager',
  'Executive',
]

const MAX_RANK = SENIORITY_LABELS.length - 1
// Paths that work backward stop at Entry-Level; Student roles are internships.
const BACKWARD_MIN_RANK = 1

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
 * Greedy path through `jobs` from `anchor`, skipping levels with no jobs.
 *
 * - `forward`: where the anchor can lead, from the anchor up to Executive.
 * - `backward`: how to reach the anchor, from Entry-Level up to the anchor.
 *
 * Either way the returned path is ordered from junior to senior.
 *
 * With `sameField`, each step prefers jobs sharing a category with the
 * previous one. Placeholder coordinates only cluster by category, so without
 * this, steps can jump to an unrelated neighboring cluster.
 */
export function careerPath(jobs, anchor, direction = 'forward', { sameField = false } = {}) {
  const path = [anchor]
  let current = anchor
  const step = direction === 'forward' ? 1 : -1
  const last = direction === 'forward' ? MAX_RANK : BACKWARD_MIN_RANK
  for (let rank = anchor.seniority_rank + step; step > 0 ? rank <= last : rank >= last; rank += step) {
    const sameFieldJobs = sameField
      ? jobs.filter((job) => job.categories.some((c) => current.categories.includes(c)))
      : []
    const [next] = nearestAtRank(sameFieldJobs, current, rank).concat(nearestAtRank(jobs, current, rank))
    if (!next) continue
    path.push(next)
    current = next
  }
  return direction === 'forward' ? path : path.reverse()
}
