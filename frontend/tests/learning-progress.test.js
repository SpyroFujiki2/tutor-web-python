import assert from 'node:assert/strict'
import { test } from 'node:test'
import { learningProgress } from '../src/services/learning-progress.js'

const lessons = [
  { id: 'video', duration_seconds: 600 },
  { id: 'exercise', duration_minutes: 5, assignment_url: 'https://example.com/work' },
]

test('video-only progress uses watch time immediately and each lesson contributes equally', () => {
  const view = learningProgress(lessons, [], [], {
    video: { duration_watched: 300 }, exercise: { duration_watched: 300 },
  }, false)
  assert.equal(view.rows[0].progress_percent, 50)
  assert.equal(view.rows[1].progress_percent, 0)
  assert.equal(view.progress_percent, 25)
  assert.equal(view.rows[1].is_completed, false)
})

test('persisted watch time is restored and stale updates cannot reduce progress', () => {
  const view = learningProgress(lessons, [{ lesson_id: 'video', duration_watched: 400 }],
    [{ lesson_id: 'video', duration_watched: 300 }], { video: { duration_watched: 20 } }, false)
  assert.equal(view.rows[0].progress_percent, 66.67)
  assert.equal(view.progress_percent, 33.33)
})

test('server assignment confirmation wins over old attendance and watching the whole video', () => {
  const confirmed = [{ lesson_id: 'exercise', assignment_completed: true }]
  const local = { video: { duration_watched: 800 }, exercise: { duration_watched: 300 } }
  const view = learningProgress(lessons, confirmed, [], local, false)
  assert.equal(view.progress_percent, 100)
  assert.equal(view.rows[1].is_completed, true)
  const revoked = learningProgress(lessons, [{ ...confirmed[0], assignment_completed: false }],
    [{ lesson_id: 'exercise', assignment_completed: true }], local, false)
  assert.equal(revoked.progress_percent, 50)
})

test('unknown duration waits for metadata instead of inventing completion', () => {
  const items = [{ id: 'unknown' }]
  const local = { unknown: { duration_watched: 30 } }
  assert.equal(learningProgress(items, [], [], local, false).progress_percent, 0)
  local.unknown.duration_seconds = 125
  assert.equal(learningProgress(items, [], [], local, false).progress_percent, 24)
})

test('live classes use attendance while assignments still need confirmation', () => {
  const records = lessons.map((lesson) => ({ lesson_id: lesson.id, is_absent: false, duration_watched: 600 }))
  assert.equal(learningProgress(lessons, [], records, {}, true).progress_percent, 50)
  records[1].assignment_completed = true
  assert.equal(learningProgress(lessons, [], records, {}, true).progress_percent, 100)
})

test('near-completion never rounds up to 100 and an empty course stays at zero', () => {
  const view = learningProgress([{ id: 'v', duration_seconds: 600000 }], [], [], { v: { duration_watched: 599999 } }, false)
  assert.equal(view.progress_percent, 99.99)
  assert.equal(view.rows[0].is_completed, false)
  assert.equal(learningProgress([], [], [], {}, false).progress_percent, 0)
})
