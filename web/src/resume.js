const MAX_RESUME_BYTES = 10 * 1024 * 1024
const MAX_PDF_PAGES = 50
const STOP_WORDS = new Set(
  `about above after again against all also among an and any are as at be because been before being below between both but by can could did do does doing down during each few for from further had has have having he her here hers herself him himself his how i if in into is it its itself just me more most my myself no nor not of off on once only or other our ours ourselves out over own same she should so some such than that the their theirs them themselves then there these they this those through to too under until up very was we were what when where which while who whom why will with would you your yours yourself yourselves a able according additionally applicant candidates candidate college degree employee employment experience five following full including job month position position requirements required satisfactory semester university year years the professional with`
    .toLowerCase()
    .split(/\s+/),
)

export async function readResume(file) {
  if (file.size > MAX_RESUME_BYTES) {
    throw new Error('Choose a resume smaller than 10 MB.')
  }

  if (file.name.toLowerCase().endsWith('.txt') || file.type === 'text/plain') {
    return file.text()
  }

  if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
    throw new Error('Choose a PDF or plain-text (.txt) resume.')
  }

  const [{ default: pdfWorkerUrl }, pdfjs] = await Promise.all([
    import('pdfjs-dist/build/pdf.worker.min.mjs?url'),
    import('pdfjs-dist'),
  ])
  pdfjs.GlobalWorkerOptions.workerSrc = pdfWorkerUrl
  const task = pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) })
  try {
    const document = await task.promise
    if (document.numPages > MAX_PDF_PAGES) {
      throw new Error(`This PDF has ${document.numPages} pages. Please use a PDF with ${MAX_PDF_PAGES} pages or fewer.`)
    }
    const pages = []
    for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber++) {
      const page = await document.getPage(pageNumber)
      const content = await page.getTextContent()
      pages.push(content.items.map((item) => ('str' in item ? item.str : '')).join(' '))
    }
    return pages.join('\n')
  } finally {
    await task.destroy()
  }
}

export function matchResumeToJobs(text, jobs) {
  const resumeTerms = extractTerms(text)
  const experienceYears = findYearsOfExperience(text)
  if (!resumeTerms.size) {
    throw new Error('Could not find readable skills or experience in this resume.')
  }

  return jobs
    .map((job) => {
      const jobText = [
        job.title,
        job.category,
        job.preferred_skills,
        job.minimum_qualifications,
      ].filter(Boolean).join(' ')
      const jobTerms = extractTerms(jobText)
      const matchedTerms = [...jobTerms]
        .filter((term) => resumeTerms.has(term))
        .sort((a, b) => b.length - a.length || a.localeCompare(b))
      const keywordScore = matchedTerms.length / Math.sqrt(Math.max(1, jobTerms.size))
      const requiredYears = findYearsOfExperience(job.minimum_qualifications || '')
      const experienceScore = experienceYears !== null && requiredYears !== null
        ? Math.min(1, experienceYears / requiredYears)
        : null
      const score = experienceScore === null
        ? keywordScore
        : keywordScore * 0.8 + experienceScore * 0.2
      return { job, score, matchedTerms: matchedTerms.slice(0, 5), experienceYears, requiredYears }
    })
    .filter((match) => match.matchedTerms.length > 0)
    .sort((a, b) => b.score - a.score || a.job.title.localeCompare(b.job.title))
}

function extractTerms(text) {
  const words = text
    .normalize('NFKD')
    .toLowerCase()
    .replace(/[\u0300-\u036f]/g, '')
    .match(/\.net|[a-z][a-z0-9+#.-]*/g) || []
  const terms = new Set()
  const relevantWords = words
    .map((word) => word.replace(/^[.-]+|[.-]+$/g, ''))
    .filter((word) => (
      (word.length >= 3 || ['c', 'r', 'c#', 'c++', '.net'].includes(word))
      && !STOP_WORDS.has(word)
    ))
  for (const word of relevantWords) terms.add(word.replace(/[.+#-]+$/g, ''))
  for (let i = 1; i < relevantWords.length; i++) {
    terms.add(`${relevantWords[i - 1]} ${relevantWords[i]}`)
  }
  return terms
}

function findYearsOfExperience(text) {
  const numberWords = {
    one: 1, two: 2, three: 3, four: 4, five: 5,
    six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
  }
  const matches = [
    ...text.matchAll(/\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\+?\s+(?:years?|yrs?)(?:\s+of)?\s+(?:(?:relevant|professional|full[-\s]?time|satisfactory)\s+)*experience\b/gi),
  ]
  const years = matches
    .map((match) => Number(match[1]) || numberWords[match[1].toLowerCase()])
    .filter((value) => value > 0 && value <= 50)
  return years.length ? Math.max(...years) : null
}
