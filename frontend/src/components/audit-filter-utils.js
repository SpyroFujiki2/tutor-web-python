import { restOperation } from './rest-operations.js'

export const emptyAuditFilters = {
  q: '', operation: '', target_type: '', actor: '', actor_kind: '', from_date: '', to_date: '',
}

function localDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(year, month - 1, day)
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day ? date : null
}

export function buildAuditQuery(values) {
  const start = values.from_date ? localDate(values.from_date) : null
  const end = values.to_date ? localDate(values.to_date) : null
  if ((values.from_date && !start) || (values.to_date && !end)) return { error: 'Ngày lọc không hợp lệ.', query: null }
  if (start && end && start > end) return { error: 'Ngày kết thúc phải bằng hoặc sau ngày bắt đầu.', query: null }
  const params = new URLSearchParams()
  for (const key of ['q', 'target_type', 'actor_kind']) {
    if (values[key]?.trim()) params.set(key, values[key].trim())
  }
  if (values.operation) params.set('operation', restOperation(values.operation))
  if (values.actor_kind !== 'system' && values.actor?.trim()) params.set('actor', values.actor.trim())
  if (start) params.set('created_from', start.toISOString())
  if (end) {
    end.setDate(end.getDate() + 1)
    params.set('created_to', end.toISOString())
  }
  return { query: params.toString(), error: '' }
}
