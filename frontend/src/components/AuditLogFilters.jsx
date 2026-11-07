import { useState } from 'react'
import { useResource } from './workspace-utils.js'
import { buildAuditQuery, emptyAuditFilters } from './audit-filter-utils.js'
import Icon from './Icon.jsx'
import { restOperations, restOperation } from './rest-operations.js'

export default function AuditLogFilters({ api, onApply }) {
  const options = useResource(api, '/admin/action-log-filters?taxonomy=rest')
  const [values, setValues] = useState(emptyAuditFilters)
  const { query, error } = buildAuditQuery(values)
  function change(event) {
    const { name, value } = event.target
    const next = { ...values, [name]: value, ...(name === 'actor_kind' && value === 'system' ? { actor: '' } : {}) }
    setValues(next)
    const result = buildAuditQuery(next)
    if (!result.error) onApply(result.query)
  }
  function submit(event) {
    event.preventDefault()
    if (error) return
    onApply(query, true)
  }
  function reset(event) {
    event.preventDefault()
    setValues(emptyAuditFilters)
    onApply('', true)
  }
  return <form className="audit-filter-form" role="search" aria-label="Tìm kiếm và lọc nhật ký" onSubmit={submit} onReset={reset}>
    <div className="audit-search-row"><label className="search-input"><Icon name="search" size={19} /><span className="sr-only">Tìm kiếm nhật ký</span><input name="q" type="search" maxLength={200} value={values.q} onChange={change} placeholder="Tìm thao tác, lý do, tài khoản hoặc mã tham chiếu…" /></label><button type="reset">Đặt lại</button></div>
    <div className="audit-filter-grid">
      <label>Thao tác REST<select name="operation" value={values.operation ? restOperation(values.operation) : ''} onChange={change}><option value="">Tất cả thao tác</option>{Object.entries(restOperations).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Thực thể<select name="target_type" value={values.target_type} onChange={change} disabled={options.loading}><option value="">Tất cả thực thể</option>{Object.entries(options.data?.entities ?? {}).sort((a, b) => a[1].localeCompare(b[1], 'vi')).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Nguồn thao tác<select name="actor_kind" value={values.actor_kind} onChange={change}><option value="">Tất cả nguồn</option><option value="user">Quản trị viên</option><option value="system">Hệ thống</option></select></label>
      <label>Người thực hiện<input name="actor" value={values.actor} onChange={change} maxLength={200} disabled={values.actor_kind === 'system'} placeholder={values.actor_kind === 'system' ? 'Không áp dụng cho hệ thống' : 'Họ tên, email hoặc mã người dùng'} /></label>
      <label>Từ ngày<input name="from_date" type="date" value={values.from_date} onChange={change} max={values.to_date || undefined} /></label>
      <label>Đến ngày<input name="to_date" type="date" value={values.to_date} onChange={change} min={values.from_date || undefined} /></label>
    </div>
    {options.error && <p role="alert" className="error-text">Chưa tải được danh sách bộ lọc. <button type="button" onClick={options.reload}>Thử lại</button></p>}
    {error && <p role="alert" className="error-text">{error}</p>}
  </form>
}
