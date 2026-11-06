import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { env } from 'node:process'
import { readFileSync } from 'node:fs'
import configureVite from '../vite.config.js'

const originalVercel = env.VERCEL
afterEach(() => {
  if (originalVercel === undefined) delete env.VERCEL
  else env.VERCEL = originalVercel
})

test('Vercel service development leaves API routing to the shared gateway', () => {
  env.VERCEL = '1'
  const config = configureVite({ mode: 'development', command: 'serve' })
  assert.equal(config.server.proxy, undefined)
})

test('standalone Vite retains the local API proxy', () => {
  delete env.VERCEL
  const config = configureVite({ mode: 'development', command: 'serve' })
  assert.equal(config.server.proxy['/api'].target, 'http://127.0.0.1:8000')
})

test('SPA deep links fall back to HTML while browser asset requests retain their paths', () => {
  const manifest = JSON.parse(readFileSync(new URL('../../vercel.json', import.meta.url), 'utf8'))
  const fallback = new RegExp(`^${manifest.services.frontend.rewrites[0].source}$`)
  for (const path of ['/', '/login', '/register', '/courses', '/tutoring', '/payment/vnpay-return', '/unknown-page']) {
    assert.equal(fallback.test(path), true, path)
  }
  for (const path of ['/favicon.svg', '/index.html', '/assets/app.js', '/assets/app.css', '/@vite/client', '/@react-refresh', '/src/main.jsx', '/node_modules/.vite/deps/react.js']) {
    assert.equal(fallback.test(path), false, path)
  }
})
