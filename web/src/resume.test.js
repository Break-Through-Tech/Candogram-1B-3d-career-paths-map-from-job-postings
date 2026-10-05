import assert from 'node:assert/strict'
import test from 'node:test'
import { matchResumeToJobs } from './resume.js'

test('ranks postings using resume keywords and years of experience', () => {
  const jobs = [
    {
      id: 'analyst',
      title: 'Data Analyst',
      category: 'Technology',
      preferred_skills: 'Python, SQL, data analysis',
      minimum_qualifications: 'Three years of professional experience',
    },
    {
      id: 'nurse',
      title: 'Registered Nurse',
      category: 'Health',
      preferred_skills: 'Patient care, nursing',
      minimum_qualifications: 'Two years of satisfactory full-time experience',
    },
  ]

  const matches = matchResumeToJobs(
    'Python SQL data analysis with 5 years of professional experience',
    jobs,
  )

  assert.equal(matches[0].job.id, 'analyst')
  assert.ok(matches[0].matchedTerms.includes('data analysis'))
  assert.ok(matches[0].matchedTerms.includes('python sql'))
  assert.equal(matches[0].experienceYears, 5)
  assert.equal(matches[0].requiredYears, 3)
  assert.equal(matches.some(({ job }) => job.id === 'nurse'), false)
})

test('extracts written years and matches role qualifications', () => {
  const [match] = matchResumeToJobs(
    'Project management and leadership. Five years of full-time experience.',
    [{
      id: 'pm',
      title: 'Project Manager',
      category: 'Management',
      preferred_skills: 'Project management and leadership',
      minimum_qualifications: 'Three years of satisfactory full-time experience',
    }],
  )

  assert.equal(match.experienceYears, 5)
  assert.equal(match.requiredYears, 3)
  assert.ok(match.matchedTerms.includes('project management'))
})

test('reports when no relevant resume terms can be extracted', () => {
  assert.throws(
    () => matchResumeToJobs('I am and was to be with you.', []),
    /Could not find readable skills or experience/,
  )
})
