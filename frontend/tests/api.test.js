import assert from 'node:assert/strict'
import { afterEach, mock, test } from 'node:test'
import { getHealth } from '../src/services/api.js'

afterEach(() => mock.restoreAll())

test('health request uses the configured API base and accepts a valid response', async () => {
  mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://api.example/api/health')
    assert.equal(options.headers.Accept, 'application/json')
    assert.ok(options.signal instanceof AbortSignal)
    return Response.json({ status: 'ok', message: 'Ready' })
  })
  assert.deepEqual(await getHealth('https://api.example'), { status: 'ok', message: 'Ready' })
})

test('empty API base requests the same origin', async () => {
  mock.method(globalThis, 'fetch', async (url) => {
    assert.equal(url, '/api/health')
    return Response.json({ status: 'ok', message: 'Ready' })
  })
  await getHealth('')
})

test('HTTP failures are reported before parsing the response body', async () => {
  mock.method(globalThis, 'fetch', async () => new Response('Unavailable', { status: 503 }))
  await assert.rejects(getHealth(''), /HTTP 503/)
})

test('an HTML response is reported as invalid JSON', async () => {
  mock.method(globalThis, 'fetch', async () => new Response('<html></html>'))
  await assert.rejects(getHealth(''), /JSON/)
})

test('unexpected JSON payloads are rejected', async () => {
  for (const payload of [null, {}, { status: 'error', message: 'No' }, { status: 'ok', message: 1 }]) {
    mock.method(globalThis, 'fetch', async () => Response.json(payload))
    await assert.rejects(getHealth(''), /không đúng định dạng/)
    mock.restoreAll()
  }
})

test('network failures preserve the original error as their cause', async () => {
  const cause = new TypeError('Failed to fetch')
  mock.method(globalThis, 'fetch', async () => { throw cause })
  await assert.rejects(getHealth(''), (error) => {
    assert.match(error.message, /Không kết nối được API/)
    assert.equal(error.cause, cause)
    return true
  })
})

test('caller cancellation reaches fetch and preserves the abort error', async () => {
  const controller = new AbortController()
  controller.abort()
  mock.method(globalThis, 'fetch', async (_url, { signal }) => {
    signal.throwIfAborted()
  })
  await assert.rejects(getHealth('', { signal: controller.signal }), { name: 'AbortError' })
})

test('timeouts produce a retryable message', async () => {
  const controller = new AbortController()
  mock.method(AbortSignal, 'timeout', (milliseconds) => {
    assert.equal(milliseconds, 10_000)
    return controller.signal
  })
  mock.method(globalThis, 'fetch', async () => {
    controller.abort()
    throw controller.signal.reason
  })
  await assert.rejects(getHealth(''), /phản hồi quá chậm/)
})

test('a timeout while reading the body is reported as a timeout', async () => {
  const controller = new AbortController()
  mock.method(AbortSignal, 'timeout', () => controller.signal)
  mock.method(globalThis, 'fetch', async () => ({
    ok: true,
    json: async () => {
      controller.abort()
      throw controller.signal.reason
    },
  }))
  await assert.rejects(getHealth(''), /phản hồi quá chậm/)
})
