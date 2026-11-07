import assert from 'node:assert/strict'
import { after, test } from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

const server = await createServer({ server: { middlewareMode: true, hmr: false }, logLevel: 'silent' })
after(() => server.close())
const { default: AdminTable } = await server.ssrLoadModule('/src/components/AdminTable.jsx')
const { default: AuditLogs } = await server.ssrLoadModule('/src/components/AuditLogs.jsx')
const { default: AuditLogFilters } = await server.ssrLoadModule('/src/components/AuditLogFilters.jsx')
const { default: WithdrawalForm } = await server.ssrLoadModule('/src/components/WithdrawalForm.jsx')
const { default: LessonMedia } = await server.ssrLoadModule('/src/components/LessonMedia.jsx')

test('user records render as a table with full names, email, status and a details action', () => {
  const html = renderToStaticMarkup(createElement(AdminTable, {
    section: 'users', onSelect() {}, rows: [{ id: 'user-1', full_name: 'Nguyễn Minh An', email: 'an@example.com', role: 'student', status: 'active' }],
  }))
  assert.match(html, /<table/)
  assert.match(html, /<thead>/)
  assert.match(html, /Nguyễn Minh An/)
  assert.match(html, /an@example.com/)
  assert.match(html, /Học viên/)
  assert.match(html, /Xem chi tiết/)
  assert.doesNotMatch(html, /<article/)
})

test('audit table renders REST categories and safely escapes reason text', () => {
  const html = renderToStaticMarkup(createElement(AuditLogs, {
    api: {}, rows: [{ id: 'log-1', operation: 'UPDATE', operation_label: 'Sửa dữ liệu', action_label: 'Thay đổi trạng thái người dùng', target_label: 'Người dùng', reason: '<script>unsafe</script>', created_at: '2026-11-07T00:00:00' }],
  }))
  assert.match(html, /<table/)
  assert.match(html, /Cập nhật một phần \(PATCH\)/)
  assert.match(html, /Thay đổi trạng thái người dùng/)
  assert.match(html, /&lt;script&gt;unsafe&lt;\/script&gt;/)
  assert.doesNotMatch(html, /<script>unsafe/)
  assert.match(html, /Xem chi tiết/)
})

test('REST dropdown renders REST verbs and normalizes stale database values', () => {
  const html = renderToStaticMarkup(createElement(AuditLogFilters, { api: {}, onApply() {} }))
  for (const value of ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OTHER']) assert.match(html, new RegExp(`value="${value}"`))
  for (const value of ['INSERT', 'SELECT', 'UPDATE']) assert.doesNotMatch(html, new RegExp(`value="${value}"`))
  assert.match(html, /Tạo mới \(POST\)/)
  assert.doesNotMatch(html, /type="submit"/)
  const stale = renderToStaticMarkup(createElement(AuditLogs, {
    api: {}, rows: [{ id: 'old-1', operation: 'UPDATE', operation_label: 'Sửa (UPDATE)', action_label: 'Thay đổi trạng thái', created_at: '2026-11-07T00:00:00' }],
  }))
  assert.match(stale, /Cập nhật một phần \(PATCH\)/)
  assert.doesNotMatch(stale, /\(UPDATE\)/)
})

test('YouTube watch links route to the embedded player while direct media stays native', () => {
  const youtube = renderToStaticMarkup(createElement(LessonMedia, { url: 'https://www.youtube.com/watch?v=VhZoXUOgHqI', title: 'Bài YouTube' }))
  assert.match(youtube, /data-youtube-video-id="VhZoXUOgHqI"/)
  assert.doesNotMatch(youtube, /<video/)
  const direct = renderToStaticMarkup(createElement(LessonMedia, { url: 'https://example.com/lesson.mp4', title: 'Bài video' }))
  assert.match(direct, /<video/)
  assert.match(direct, /src="https:\/\/example.com\/lesson.mp4"/)
})

test('withdrawal UI excludes normal wallets and allows only an eligible commercial wallet', () => {
  const banks = [{ id: 'bank-1', bank_name: 'Example Bank', account_number_masked: '****1234' }]
  const normal = { id: 'normal-1', type: 'normal', is_active: true, debt: 0, spendable_balance: 1000 }
  const blocked = renderToStaticMarkup(createElement(WithdrawalForm, { wallets: [normal], banks, onSubmit() {} }))
  assert.doesNotMatch(blocked, /<form/)
  assert.match(blocked, /Ví cá nhân không hỗ trợ rút tiền/)
  const commercial = { id: 'commercial-1', type: 'commercial', is_active: true, debt: 0, spendable_balance: 500 }
  const eligible = renderToStaticMarkup(createElement(WithdrawalForm, { wallets: [normal, commercial], banks, onSubmit() {} }))
  assert.match(eligible, /Tạo đơn rút/)
  assert.doesNotMatch(eligible, /value="normal"/)
  const debt = renderToStaticMarkup(createElement(WithdrawalForm, { wallets: [{ ...commercial, debt: 10 }], banks, onSubmit() {} }))
  assert.doesNotMatch(debt, /<form/)
})
