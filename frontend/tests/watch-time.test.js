import assert from 'node:assert/strict'
import { test } from 'node:test'
import { playbackDelta, formatDuration } from '../src/services/watch-time.js'

test('watch time counts playback and playback speed, excluding seeking', () => {
  assert.equal(playbackDelta(10, 10.25, 0.25), 0.25)
  assert.equal(playbackDelta(10, 10.5, 0.25, 2), 0.5)
  assert.equal(playbackDelta(10, 300, 0.25), 0)
  assert.equal(playbackDelta(300, 10, 0.25), 0)
  assert.equal(playbackDelta(10, 10, 5), 0)
})

test('duration formatting handles metadata that is not yet available', () => {
  assert.equal(formatDuration(null), '—')
  assert.equal(formatDuration(Infinity), '—')
  assert.equal(formatDuration(0), '0:00')
  assert.equal(formatDuration(125.8), '2:05')
})
