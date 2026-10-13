export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
}

/** $58,714 -> "$58.7k", $120,000 -> "$120k" */
export function compactMoney(amount) {
  if (amount == null) return ''
  if (amount < 1000) return `$${Math.round(amount)}`
  const thousands = amount / 1000
  return `$${thousands >= 100 ? Math.round(thousands) : +thousands.toFixed(1)}k`
}

export function salaryRange(job) {
  if (job.salary_from == null && job.salary_to == null) return 'Salary not listed'
  if (job.salary_from == null || job.salary_from === job.salary_to) return `${compactMoney(job.salary_to)}/yr`
  return `${compactMoney(job.salary_from)}–${compactMoney(job.salary_to)}/yr`
}

export function median(values) {
  const sorted = values.filter((v) => v != null).sort((a, b) => a - b)
  if (!sorted.length) return null
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}
