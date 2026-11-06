import assert from 'node:assert/strict'
import { test } from 'node:test'
import { filterCollection, loadCollection, matchesPrice } from '../src/components/collection-utils.js'
import { loginDestination, resolveRoute, returnDestination } from '../src/navigation.js'

test('course search combines accent-insensitive content, format and price filters', () => {
  const courses = [
    { id: '1', title: 'Nhập môn lập trình', description: 'Python cơ bản', is_live: false, price: 200 },
    { id: '2', title: 'Python trực tiếp', is_live: true, price: 0 },
    { id: '3', title: 'Lập trình web', description: 'JavaScript', is_live: false, price: 400 },
  ]
  assert.deepEqual(filterCollection(courses, { query: 'PYTHON', format: 'video', price: 'paid' }).map((row) => row.id), ['1'])
  assert.deepEqual(filterCollection(courses, { query: 'lap trinh' }).map((row) => row.id), ['1', '3'])
  assert.deepEqual(filterCollection(courses, { format: 'live', price: 'free' }).map((row) => row.id), ['2'])
  assert.equal(filterCollection(courses, { query: 'không tồn tại' }).length, 0)
})

test('package prices have unambiguous boundaries and sorting preserves source order', () => {
  assert.equal(matchesPrice(499, 'under500'), true)
  assert.equal(matchesPrice(500, 'under500'), false)
  assert.equal(matchesPrice(500, '500to1000'), true)
  assert.equal(matchesPrice(1000, '500to1000'), true)
  assert.equal(matchesPrice(1000, 'over1000'), false)
  assert.equal(matchesPrice(1001, 'over1000'), true)
  const rows = [{ id: 'a', price: 800 }, { id: 'b', price: 200 }]
  assert.deepEqual(filterCollection(rows, { sort: 'price_asc' }).map((row) => row.id), ['b', 'a'])
  assert.deepEqual(rows.map((row) => row.id), ['a', 'b'])
})

test('post filters combine author and content search with chronological sorting', () => {
  const rows = [
    { id: '1', author_id: 'me', content: 'Kinh nghiệm học Python', created_at: '2026-11-01T00:00:00Z' },
    { id: '2', author_id: 'other', content: 'Python', created_at: '2026-11-03T00:00:00Z' },
    { id: '3', author_id: 'me', content: 'Hỏi đáp Python', created_at: '2026-11-02T00:00:00Z' },
  ]
  assert.deepEqual(filterCollection(rows, { query: 'python', author: 'mine', userId: 'me', sort: 'newest' }).map((row) => row.id), ['3', '1'])
})

test('collection loading searches beyond the first 100 records', async () => {
  const signal = new AbortController().signal
  const paths = []
  const api = { request: async (path, options) => {
    paths.push(path)
    assert.equal(options.signal, signal)
    const offset = Number(new URL(path, 'https://example.test').searchParams.get('offset'))
    return Array.from({ length: offset === 200 ? 1 : 100 }, (_, index) => ({ id: String(offset + index), title: offset === 200 ? 'Python cuối danh sách' : 'Khóa học' }))
  } }
  const rows = await loadCollection(api, '/courses', signal)
  assert.equal(rows.length, 201)
  assert.deepEqual(paths, ['/courses?limit=100&offset=0', '/courses?limit=100&offset=100', '/courses?limit=100&offset=200'])
  assert.equal(filterCollection(rows, { query: 'cuoi danh sach' })[0].id, '200')
})

test('collection loader rejects malformed, repeated and failed pages', async () => {
  await assert.rejects(loadCollection({ request: async () => ({ items: [] }) }, '/courses'), /định dạng/)
  const repeated = Array.from({ length: 100 }, (_, id) => ({ id }))
  await assert.rejects(loadCollection({ request: async () => repeated }, '/courses'), /trang tiếp theo/)
  await assert.rejects(loadCollection({ request: async () => { throw new Error('Offline') } }, '/courses'), /Offline/)
})

test('auth redirects retain only known local destinations', () => {
  assert.equal(resolveRoute('/login').auth, true)
  assert.equal(resolveRoute('/courses/').page, 'catalog')
  assert.equal(resolveRoute('/wallet').protected, true)
  assert.equal(resolveRoute('/tutoring').protected, undefined)
  assert.equal(resolveRoute('/unknown').page, 'not-found')
  assert.equal(returnDestination('?next=%2Fwallet'), '/wallet')
  assert.equal(returnDestination('?next=%2Fcourses%3Fview%3Dall'), '/courses?view=all')
  assert.equal(returnDestination('?next=https%3A%2F%2Fevil.example'), '/learning')
  assert.equal(returnDestination('?next=%2F%2Fevil.example'), '/learning')
  assert.equal(returnDestination('?next=%2Flogin'), '/learning')
  assert.equal(returnDestination('?next=%2Fpayment%2Fvnpay-return'), '/learning')
  assert.equal(returnDestination('?next=%2F%5Cevil.example'), '/learning')
  assert.equal(loginDestination('/community'), '/login?next=%2Fcommunity')
})
