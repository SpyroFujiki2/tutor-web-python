import assert from 'node:assert/strict'
import { afterEach, mock, test } from 'node:test'
import { ApiError, createApiClient } from '../src/services/api.js'
import { SESSION_KEY } from '../src/services/session.js'
import { Buffer } from 'node:buffer'

afterEach(() => mock.restoreAll())

test('authenticated mutation sends JSON and accepts an empty 204', async () => {
  const client = createApiClient('https://api.example')
  client.setTokens({ access_token: 'access', refresh_token: 'refresh' })
  mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://api.example/api/me/payment-methods/example')
    assert.equal(options.headers.Authorization, 'Bearer access')
    assert.equal(options.method, 'DELETE')
    return new Response(null, { status: 204 })
  })
  assert.equal(await client.request('/me/payment-methods/example', { method: 'DELETE' }), null)
})

test('concurrent expired requests rotate the refresh token only once', async () => {
  const client = createApiClient('')
  client.setTokens({ access_token: 'old', refresh_token: 'refresh-old' })
  let refreshes = 0
  mock.method(globalThis, 'fetch', async (url, options) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes++
      assert.deepEqual(JSON.parse(options.body), { refresh_token: 'refresh-old' })
      await new Promise((resolve) => setTimeout(resolve, 5))
      return Response.json({ access_token: 'new', refresh_token: 'refresh-new' })
    }
    return options.headers.Authorization === 'Bearer old'
      ? Response.json({ detail: 'Expired' }, { status: 401 })
      : Response.json({ ok: true })
  })
  const results = await Promise.all([client.request('/bookings'), client.request('/me/wallets')])
  assert.equal(refreshes, 1)
  assert.deepEqual(results, [{ ok: true }, { ok: true }])
})

test('failed refresh clears the session and notifies once', async () => {
  let notifications = 0
  const client = createApiClient('', { onUnauthorized: () => notifications++ })
  client.setTokens({ access_token: 'old', refresh_token: 'old-refresh' })
  mock.method(globalThis, 'fetch', async () => Response.json({ detail: 'Expired' }, { status: 401 }))
  await assert.rejects(client.request('/bookings'), (error) => error instanceof ApiError && error.status === 401)
  assert.equal(notifications, 1)
  mock.restoreAll()
  mock.method(globalThis, 'fetch', async (_url, options) => {
    assert.equal(options.headers.Authorization, undefined)
    return Response.json([])
  })
  await client.request('/courses')
})

test('logout during rotation cannot restore the old session', async () => {
  const client = createApiClient('')
  client.setTokens({ access_token: 'old', refresh_token: 'old-refresh' })
  let startRefresh
  const started = new Promise((resolve) => { startRefresh = resolve })
  let finishRefresh
  mock.method(globalThis, 'fetch', async (url) => {
    if (url.endsWith('/auth/refresh')) {
      startRefresh()
      return new Promise((resolve) => { finishRefresh = resolve })
    }
    return Response.json({ detail: 'Expired' }, { status: 401 })
  })
  const pending = client.request('/bookings')
  await started
  client.setTokens(null)
  finishRefresh(Response.json({ access_token: 'new', refresh_token: 'new-refresh' }))
  await assert.rejects(pending, (error) => error.status === 401)
})

test('validation errors are readable and forbidden writes are never retried', async () => {
  let calls = 0
  const client = createApiClient('')
  client.setTokens({ access_token: 'access', refresh_token: 'refresh' })
  mock.method(globalThis, 'fetch', async () => {
    calls++
    return Response.json({ detail: [{ loc: ['body', 'price'], msg: 'Must be positive' }] }, { status: 422 })
  })
  await assert.rejects(client.request('/admin/courses', { method: 'POST', body: { price: -1 } }), /price: Must be positive/)
  assert.equal(calls, 1)
})

test('network failures do not automatically retry financial mutations', async () => {
  let calls = 0
  const client = createApiClient('')
  mock.method(globalThis, 'fetch', async () => { calls++; throw new TypeError('Failed to fetch') })
  await assert.rejects(client.request('/me/deposits', { method: 'POST', body: { request_id: 'same-id' } }), /Không kết nối/)
  assert.equal(calls, 1)
})

test('login failures never attempt token rotation', async () => {
  const client = createApiClient('')
  client.setTokens({ access_token: 'access', refresh_token: 'refresh' })
  const paths = []
  mock.method(globalThis, 'fetch', async (url) => {
    paths.push(url)
    return Response.json({ detail: 'Invalid email or password' }, { status: 401 })
  })
  await assert.rejects(client.request('/auth/login', { method: 'POST', body: {} }), /Invalid email/)
  assert.deepEqual(paths, ['/api/auth/login'])
})

test('protected auth endpoints can refresh an expired access token', async () => {
  const client = createApiClient('')
  client.setTokens({ access_token: 'old', refresh_token: 'refresh' })
  mock.method(globalThis, 'fetch', async (url, options) => {
    if (url.endsWith('/auth/refresh')) return Response.json({ access_token: 'new', refresh_token: 'new-refresh' })
    return options.headers.Authorization === 'Bearer old'
      ? Response.json({ detail: 'Expired' }, { status: 401 })
      : new Response(null, { status: 204 })
  })
  assert.equal(await client.request('/auth/logout', { method: 'POST' }), null)
})

test('private attachments upload raw bytes and download with authorization', async () => {
  const client = createApiClient('')
  client.setTokens({ access_token: 'access', refresh_token: 'refresh' })
  const blob = new Blob(['%PDF-1.7\nfixture'], { type: 'application/pdf' })
  mock.method(globalThis, 'fetch', async (_url, options) => {
    assert.equal(options.headers.Authorization, 'Bearer access')
    if (options.method === 'POST') {
      assert.equal(options.body, blob)
      assert.equal(options.headers['Content-Type'], 'application/pdf')
      return Response.json({ id: 1, file_url: '/api/bookings/example/attachments/file.pdf' })
    }
    return new Response(blob, { headers: { 'Content-Type': 'application/pdf' } })
  })
  await client.request('/bookings/example/attachments?name=fixture.pdf', { method: 'POST', rawBody: blob, contentType: blob.type })
  assert.equal(await (await client.request('/bookings/example/attachments/file.pdf', { responseType: 'blob' })).text(), '%PDF-1.7\nfixture')
})

function memoryStorage() {
  const data = new Map()
  return { getItem: (key) => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: (key) => data.delete(key) }
}

const sessionKey = `${SESSION_KEY}:same-origin`
const token = (sid, version) => `header.${Buffer.from(JSON.stringify({ sid })).toString('base64url')}.${version}`
const pair = (sid, version) => ({ access_token: token(sid, `access-${version}`), refresh_token: token(sid, `refresh-${version}`) })

test('a new client restores a saved login after reload and logout removes it', async () => {
  const storage = memoryStorage()
  const first = createApiClient('', { storage })
  first.setTokens(pair('session-one', 1))
  const reloaded = createApiClient('', { storage })
  assert.equal(reloaded.hasSession(), true)
  mock.method(globalThis, 'fetch', async (_url, options) => {
    assert.equal(options.headers.Authorization, `Bearer ${pair('session-one', 1).access_token}`)
    return Response.json({ id: 'user-one' })
  })
  assert.deepEqual(await reloaded.request('/auth/me'), { id: 'user-one' })
  reloaded.setTokens(null)
  assert.equal(storage.getItem(sessionKey), null)
  assert.equal(first.hasSession(), false)
  assert.equal(createApiClient('', { storage }).hasSession(), false)
})

test('expired credentials are rotated and saved for the next page load', async () => {
  const storage = memoryStorage()
  const client = createApiClient('', { storage })
  client.setTokens(pair('one', 1))
  mock.method(globalThis, 'fetch', async (url, options) => {
    if (url.endsWith('/auth/refresh')) return Response.json(pair('one', 2))
    return options.headers.Authorization === `Bearer ${pair('one', 1).access_token}`
      ? Response.json({ detail: 'Expired' }, { status: 401 }) : Response.json({ ok: true })
  })
  await client.request('/auth/me')
  assert.deepEqual(JSON.parse(storage.getItem(sessionKey)), pair('one', 2))
  assert.deepEqual(await createApiClient('', { storage }).request('/auth/me'), { ok: true })
})

test('a temporary refresh outage preserves the login and can recover', async () => {
  const storage = memoryStorage()
  let unauthorized = 0
  let offline = true
  const client = createApiClient('', { storage, onUnauthorized: () => unauthorized++ })
  client.setTokens(pair('one', 1))
  mock.method(globalThis, 'fetch', async (url, options) => {
    if (url.endsWith('/auth/refresh')) {
      if (offline) throw new TypeError('offline')
      return Response.json(pair('one', 2))
    }
    return options.headers.Authorization === `Bearer ${pair('one', 1).access_token}`
      ? Response.json({ detail: 'Expired' }, { status: 401 }) : Response.json({ ok: true })
  })
  await assert.rejects(client.request('/auth/me'), /Không kết nối/)
  assert.equal(unauthorized, 0)
  assert.equal(client.hasSession(), true)
  assert.deepEqual(JSON.parse(storage.getItem(sessionKey)), pair('one', 1))
  offline = false
  assert.deepEqual(await client.request('/auth/me'), { ok: true })
})

test('two browser tabs serialize single-use refresh and both keep working', async () => {
  const storage = memoryStorage()
  let queue = Promise.resolve()
  const locks = { request: (_key, work) => {
    const result = queue.then(work)
    queue = result.catch(() => {})
    return result
  } }
  const first = createApiClient('', { storage, locks })
  first.setTokens(pair('one', 1))
  const second = createApiClient('', { storage, locks })
  let refreshes = 0
  mock.method(globalThis, 'fetch', async (url, options) => {
    if (url.endsWith('/auth/refresh')) {
      refreshes++
      assert.deepEqual(JSON.parse(options.body), { refresh_token: pair('one', 1).refresh_token })
      await new Promise((resolve) => setTimeout(resolve, 5))
      return Response.json(pair('one', 2))
    }
    return options.headers.Authorization === `Bearer ${pair('one', 1).access_token}`
      ? Response.json({ detail: 'Expired' }, { status: 401 }) : Response.json({ ok: true })
  })
  assert.deepEqual(await Promise.all([first.request('/auth/me'), second.request('/me/wallets')]), [{ ok: true }, { ok: true }])
  assert.equal(refreshes, 1)
  assert.equal(first.hasSession(), true)
  assert.equal(second.hasSession(), true)
})

test('logout in another tab during refresh cannot restore the removed session', async () => {
  const storage = memoryStorage()
  const first = createApiClient('', { storage })
  first.setTokens(pair('one', 1))
  const second = createApiClient('', { storage })
  let startRefresh, finishRefresh
  const started = new Promise((resolve) => { startRefresh = resolve })
  mock.method(globalThis, 'fetch', async (url) => {
    if (url.endsWith('/auth/refresh')) {
      startRefresh()
      return new Promise((resolve) => { finishRefresh = resolve })
    }
    return Response.json({ detail: 'Expired' }, { status: 401 })
  })
  const pending = first.request('/auth/me')
  await started
  second.setTokens(null)
  finishRefresh(Response.json(pair('one', 2)))
  await assert.rejects(pending, (error) => error.status === 401)
  assert.equal(storage.getItem(sessionKey), null)
  assert.equal(first.hasSession(), false)
})

test('storage events synchronize sign-out and listeners are cleaned up', () => {
  const storage = memoryStorage()
  const events = new EventTarget()
  const client = createApiClient('', { storage, eventTarget: events })
  client.setTokens(pair('one', 1))
  let changes = 0
  const unsubscribe = client.subscribeSession(() => changes++)
  storage.removeItem(sessionKey)
  const changed = new Event('storage')
  Object.defineProperty(changed, 'key', { value: sessionKey })
  events.dispatchEvent(changed)
  assert.equal(changes, 1)
  assert.equal(client.hasSession(), false)
  unsubscribe()
  storage.setItem(sessionKey, JSON.stringify(pair('two', 1)))
  events.dispatchEvent(changed)
  assert.equal(changes, 1)
})

test('blocked or corrupted browser storage still allows an in-memory login', async () => {
  const storage = { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') }, removeItem: () => { throw new Error('blocked') } }
  const client = createApiClient('', { storage })
  assert.equal(client.hasSession(), false)
  client.setTokens(pair('one', 1))
  mock.method(globalThis, 'fetch', async (_url, options) => {
    assert.equal(options.headers.Authorization, `Bearer ${pair('one', 1).access_token}`)
    return Response.json({ ok: true })
  })
  assert.deepEqual(await client.request('/auth/me'), { ok: true })
  const corrupted = memoryStorage()
  corrupted.setItem(sessionKey, '{broken-json')
  assert.equal(createApiClient('', { storage: corrupted }).hasSession(), false)
  corrupted.setItem(sessionKey, JSON.stringify({ access_token: 'access-only' }))
  assert.equal(createApiClient('', { storage: corrupted }).hasSession(), false)
})
