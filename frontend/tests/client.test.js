import assert from 'node:assert/strict'
import { afterEach, mock, test } from 'node:test'
import { ApiError, createApiClient } from '../src/services/api.js'

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
