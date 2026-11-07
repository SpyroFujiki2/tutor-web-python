import assert from 'node:assert/strict'
import { test } from 'node:test'
import { buildAuditQuery, emptyAuditFilters } from '../src/components/audit-filter-utils.js'

test('combined REST filters keep exact values and encode search text safely', () => {
  const { query, error } = buildAuditQuery({ ...emptyAuditFilters, operation: 'PATCH', target_type: 'users', q: '  Họ tên & lý do  ', actor: ' admin@example.com ', actor_kind: 'user' })
  const params = new URLSearchParams(query)
  assert.equal(error, '')
  assert.equal(params.get('operation'), 'PATCH')
  assert.equal(params.get('target_type'), 'users')
  assert.equal(params.get('q'), 'Họ tên & lý do')
  assert.equal(params.get('actor'), 'admin@example.com')
})

test('system filtering removes stale administrator constraints and reset clears every field', () => {
  const params = new URLSearchParams(buildAuditQuery({ ...emptyAuditFilters, actor: 'admin', actor_kind: 'system' }).query)
  assert.equal(params.has('actor'), false)
  assert.equal(params.get('actor_kind'), 'system')
  assert.equal(buildAuditQuery(emptyAuditFilters).query, '')
})

test('old selections are normalized to REST operations before sending a filter', () => {
  for (const [old, current] of [['SELECT', 'GET'], ['INSERT', 'POST'], ['UPDATE', 'PATCH'], ['PUT', 'PUT']]) {
    const params = new URLSearchParams(buildAuditQuery({ ...emptyAuditFilters, operation: old }).query)
    assert.equal(params.get('operation'), current)
  }
})

test('date filters include the whole final local day and reject invalid ranges', () => {
  const { query, error } = buildAuditQuery({ ...emptyAuditFilters, from_date: '2026-11-07', to_date: '2026-11-07' })
  assert.equal(error, '')
  const params = new URLSearchParams(query)
  const start = new Date(params.get('created_from'))
  const end = new Date(params.get('created_to'))
  assert.equal(start.getDate(), 7)
  assert.equal(start.getHours(), 0)
  assert.equal(end.getDate(), 8)
  assert.equal(end.getHours(), 0)
  assert.ok(buildAuditQuery({ ...emptyAuditFilters, from_date: '2026-11-09', to_date: '2026-11-07' }).error)
  assert.ok(buildAuditQuery({ ...emptyAuditFilters, from_date: '2026-02-30' }).error)
})
