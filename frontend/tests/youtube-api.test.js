import assert from 'node:assert/strict'
import { test } from 'node:test'
import { loadYouTubeApi, youtubeErrorMessage } from '../src/services/youtube-api.js'

test('YouTube SDK load failures can retry, and concurrent players share a single script', async () => {
  const originalWindow = globalThis.window
  const originalDocument = globalThis.document
  const scripts = []
  let previousReadyCalls = 0
  const previous = () => previousReadyCalls++
  globalThis.window = { onYouTubeIframeAPIReady: previous }
  globalThis.document = {
    createElement: () => ({ remove() { this.removed = true } }),
    head: { appendChild: (script) => scripts.push(script) },
  }
  try {
    const failed = loadYouTubeApi()
    const rejected = assert.rejects(failed, /unavailable/)
    scripts[0].onerror()
    await rejected
    assert.equal(scripts[0].removed, true)
    const first = loadYouTubeApi()
    assert.equal(loadYouTubeApi(), first)
    assert.equal(scripts.length, 2)
    assert.equal(scripts[1].src, 'https://www.youtube.com/iframe_api')
    assert.equal(scripts[1].referrerPolicy, 'strict-origin-when-cross-origin')
    globalThis.window.YT = { Player: class {} }
    globalThis.window.onYouTubeIframeAPIReady()
    assert.equal(await first, globalThis.window.YT)
    assert.equal(previousReadyCalls, 1)
    assert.equal(globalThis.window.onYouTubeIframeAPIReady, previous)
  } finally {
    if (originalWindow === undefined) delete globalThis.window
    else globalThis.window = originalWindow
    if (originalDocument === undefined) delete globalThis.document
    else globalThis.document = originalDocument
  }
})

test('YouTube errors distinguish unavailable content from disabled embedding', () => {
  assert.match(youtubeErrorMessage(100), /riêng tư/)
  assert.match(youtubeErrorMessage(101), /không cho phép phát/)
  assert.equal(youtubeErrorMessage(150), youtubeErrorMessage(101))
  assert.match(youtubeErrorMessage(153), /thử lại/)
})
