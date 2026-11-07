import { useState } from 'react'
import { date, useResource } from './workspace-utils.js'
import ContentDialog from './ContentDialog.jsx'
import { Resource } from './Workspace.jsx'
import { auditChanges } from './audit-utils.js'
import DataTable from './DataTable.jsx'
import { restOperation, restOperationLabel } from './rest-operations.js'

function Person({ user, id, system = false, compact = false }) {
  if (!id) return <span>{system ? 'Hệ thống' : '—'}</span>
  return <div className="audit-person"><strong>{user?.full_name || user?.email || 'Không còn thông tin tài khoản'}</strong>{user?.full_name && user.email && <span>{user.email}</span>}{!compact && <code>{id}</code>}</div>
}

function Snapshot({ title, value }) {
  return <section className="audit-snapshot"><h4>{title}</h4><pre>{value == null ? 'Không có dữ liệu' : JSON.stringify(value, null, 2)}</pre></section>
}

export default function AuditLogs({ api, rows }) {
  const [selected, setSelected] = useState(null)
  const columns = [
    { key: 'created_at', label: 'Thời gian', render: (row) => date(row.created_at) },
    { key: 'operation', label: 'Thao tác REST', render: (row) => <span className={`audit-operation operation-${restOperation(row.operation, row.action_code)}`}>{restOperationLabel(row.operation, row.action_code)}</span> },
    { key: 'action', label: 'Hành động', render: (row) => <span title={row.action_code}>{row.action_label || row.action_code || 'Thao tác hệ thống'}</span> },
    { key: 'admin', label: 'Người thực hiện', render: (row) => <Person user={row.admin} id={row.admin_id} system compact /> },
    { key: 'target', label: 'Thực thể', render: (row) => row.target_label || row.target_type || '—' },
    { key: 'reason', label: 'Lý do', render: (row) => row.reason_label || row.reason || '—' },
    { key: 'details', label: 'Chi tiết', render: (row) => <button className="table-action" onClick={() => setSelected(row.id)}>Xem chi tiết</button> },
  ]
  return <><DataTable label="Nhật ký hoạt động" rows={rows} columns={columns} />{selected && <AuditLogDetail key={selected} api={api} id={selected} onClose={() => setSelected(null)} />}</>
}

function AuditLogDetail({ api, id, onClose }) {
  const resource = useResource(api, `/admin/action-logs/${id}`)
  return <ContentDialog title="CHI TIẾT NHẬT KÝ HOẠT ĐỘNG" className="audit-detail-dialog" onClose={onClose}><Resource resource={resource}>{(row) => {
    const changes = auditChanges(row.old_value, row.new_value)
    return <><h2>{row.action_label || row.action_code}</h2><dl className="audit-detail-metadata">
      <div><dt>Thao tác REST</dt><dd>{restOperationLabel(row.operation, row.action_code)}</dd></div>
      <div><dt>Thời gian</dt><dd>{date(row.created_at)}</dd></div>
      <div><dt>Người thực hiện</dt><dd><Person user={row.admin} id={row.admin_id} system /></dd></div>
      <div><dt>Người dùng liên quan</dt><dd><Person user={row.target_user} id={row.target_user_id} /></dd></div>
      <div><dt>Thực thể</dt><dd>{row.target_label}<code>{row.target_type}</code></dd></div>
      <div><dt>Mã đối tượng</dt><dd><code>{row.target_id || '—'}</code></dd></div>
      <div><dt>Mã nhật ký</dt><dd><code>{row.id}</code></dd></div>
      <div><dt>Mã hành động</dt><dd><code>{row.action_code || '—'}</code></dd></div>
    </dl><p className="audit-reason"><strong>Lý do:</strong> {row.reason_label || row.reason || '—'}</p>
      {row.operation === 'OTHER' && <p className="muted">Thao tác không thuộc nhóm Thêm, Xem, Sửa hoặc Xóa dữ liệu.</p>}
      <h3>Dữ liệu thay đổi</h3>{changes.length ? <div className="audit-diff-wrap"><table className="audit-diff"><thead><tr><th>Thông tin</th><th>Trước</th><th>Sau</th></tr></thead><tbody>{changes.map((change) => <tr key={change.key} className={change.changed ? 'is-changed' : ''}><th scope="row">{change.label}</th><td>{change.before}</td><td>{change.after}</td></tr>)}</tbody></table></div> : <p className="muted">Thao tác không có dữ liệu trước/sau được ghi nhận.</p>}
      <details className="audit-raw"><summary>Dữ liệu gốc</summary><div className="audit-changes"><Snapshot title="Trước thay đổi" value={row.old_value} /><Snapshot title="Sau thay đổi" value={row.new_value} /></div></details>
    </>
  }}</Resource></ContentDialog>
}
