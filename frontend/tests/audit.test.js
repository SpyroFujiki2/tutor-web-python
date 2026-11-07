import assert from 'node:assert/strict'
import { test } from 'node:test'
import { auditChanges, auditValue } from '../src/components/audit-utils.js'

test('audit comparisons preserve removed fields, null, false and unchanged values', () => {
  const rows = auditChanges({ status: 'active', is_active: false, reason: null, name: 'Old' }, { status: 'suspended', is_active: false, amount: 0 })
  assert.deepEqual(rows.map((row) => row.key), ['status', 'is_active', 'reason', 'name', 'amount'])
  assert.equal(rows[0].before, 'Hoạt động')
  assert.equal(rows[0].after, 'Tạm khóa')
  assert.equal(rows[1].changed, false)
  assert.equal(rows[1].before, 'Không')
  assert.equal(rows[2].before, '—')
  assert.equal(rows[2].after, 'Chưa có')
  assert.equal(rows[4].after, '0')
  assert.deepEqual(auditChanges(null, null), [])
})

test('audit values preserve arbitrary text and structured reference data', () => {
  assert.equal(auditValue('__proto__'), '__proto__')
  assert.equal(auditValue('<script>example</script>'), '<script>example</script>')
  assert.equal(auditValue(['one', 'two']), '[\n  "one",\n  "two"\n]')
})
