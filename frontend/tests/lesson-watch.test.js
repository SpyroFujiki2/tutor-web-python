import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createLessonWatch } from '../src/services/lesson-watch.js'

test('watch recorder follows playback and duration while excluding pauses and seek jumps', async () => {
  let time = 0
  const requests = []
  const changes = []
  const recorder = createLessonWatch({
    enabled: true, clock: () => time, initialWatched: 20,
    api: { request: async (path, options) => { requests.push({ path, ...options }); return { progress_percent: '0' } } },
    path: '/subscriptions/s/lessons/l/watch', cacheKey: 'test', url: 'https://youtube.com/watch?v=VhZoXUOgHqI',
    onWatch: (...values) => changes.push(values),
  })
  const play = (currentTime, playing = true) => recorder.observe({ currentTime, playing, duration: 180, playbackRate: 1 })
  play(0)
  time = 1000; play(1)
  assert.deepEqual(changes.at(-1), [21, false, 180])
  assert.equal(requests.length, 0)
  time = 2000; play(120)
  time = 3000; play(121, false)
  time = 9000; play(121, false)
  assert.deepEqual(changes.at(-1), [22, false, 180])
  assert.equal(recorder.snapshot().watched, 22)
  await recorder.save()
  await recorder.save()
  assert.equal(requests.length, 1)
  assert.equal(requests[0].body.duration_watched, 22)
  assert.equal(requests[0].body.duration_seconds, 180)
  assert.equal(requests[0].body.completed, false)
  assert.equal(requests[0].keepalive, true)
})

test('failed autosaves retry the same progress, preserve browser recovery and keep grading server-side', async () => {
  let attempts = 0
  let time = 0
  const cache = new Map([['lesson', JSON.stringify({ url: 'video', seconds: 40 })]])
  const recorder = createLessonWatch({ enabled: true, initialWatched: 10, cacheKey: 'lesson', url: 'video',
    storage: { getItem: (key) => cache.get(key), setItem: (key, value) => cache.set(key, value) },
    clock: () => time, path: '/watch', api: { request: async () => { if (++attempts === 1) throw new Error('offline'); return {} } },
  })
  recorder.observe({ currentTime: 0, playing: true, playbackRate: 2, duration: 50 })
  time = 1000
  recorder.observe({ currentTime: 2, playing: true, playbackRate: 2, duration: 50 })
  await recorder.save()
  await recorder.save()
  assert.equal(attempts, 2)
  assert.equal(recorder.snapshot().watched, 42)
  assert.equal(JSON.parse(cache.get('lesson')).seconds, 42)
})

test('live or inaccessible learning content does not submit watch records', async () => {
  let requests = 0
  const recorder = createLessonWatch({ enabled: false, api: { request: async () => { requests++ } } })
  recorder.observe({ currentTime: 90, duration: 180, playing: true })
  await recorder.save()
  assert.equal(requests, 0)
  assert.equal(recorder.snapshot().duration, 180)
  assert.equal(recorder.snapshot().watched, 0)
})
