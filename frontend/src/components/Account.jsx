import { Action, Details, Form, Resource } from './Workspace.jsx'
import { date, textField, useResource } from './workspace-utils.js'
import PageHeading from './PageHeading.jsx'

export default function Account({ api, user, onLogout, onProfileChange }) {
  const roles = useResource(api, '/me/role-requests?limit=100')
  const reports = useResource(api, '/me/reports?limit=100')
  const settlements = useResource(api, '/me/settlements?limit=100')
  const sessions = useResource(api, '/auth/sessions')
  return <section className="account-page"><PageHeading eyebrow="KHÔNG GIAN RIÊNG CỦA BẠN" title="Tài khoản & bảo mật" description="Cập nhật thông tin, quản lý các phiên đăng nhập và theo dõi yêu cầu của bạn." icon="settings" /><div className="split"><div className="card card-body"><h2>Thông tin cá nhân</h2><Details row={{ ...user, full_name: user.full_name || 'Chưa cập nhật' }} fields={['full_name', 'email', 'role', 'status']} />
    <details><summary>Cập nhật họ tên</summary><Form fields={[textField('full_name', 'Họ và tên', { maxLength: 200, autoComplete: 'name' })]} initial={user} submit="Lưu họ tên" onSubmit={async (values) => { const updated = await api.request('/auth/profile', { method: 'PATCH', body: values }); onProfileChange(updated) }} /></details>
    <details><summary>Đổi mật khẩu</summary><Form fields={[
      textField('old_password', 'Mật khẩu hiện tại', { type: 'password', autoComplete: 'current-password' }),
      textField('new_password', 'Mật khẩu mới', { type: 'password', minLength: 8, autoComplete: 'new-password' }),
    ]} submit="Đổi mật khẩu và đăng xuất" onSubmit={async (values) => { await api.request('/auth/change-password', { method: 'POST', body: values }); onLogout() }} /></details>
    <details><summary>Đổi email</summary><p>Đổi email sẽ đăng xuất các phiên hiện tại. Dùng email mới để đăng nhập lại.</p><Form fields={[
      textField('email', 'Email mới', { type: 'email', autoComplete: 'email', maxLength: 320 }),
      textField('password', 'Mật khẩu hiện tại', { type: 'password', autoComplete: 'current-password' }),
    ]} submit="Đổi email và đăng xuất" onSubmit={async (values) => { await api.request('/auth/change-email', { method: 'POST', body: values }); onLogout() }} /></details>
    <Action onClick={async () => { await api.request('/auth/logout-all', { method: 'POST' }); onLogout() }}>Đăng xuất mọi thiết bị</Action>
  </div><div className="card card-body"><h2>Đề nghị nâng bậc</h2><p>Mỗi yêu cầu nâng một bậc và cần quản trị xét duyệt.</p>
    {user.role !== 'head_admin' && <Form fields={[textField('request_note', 'Giới thiệu & lý do', { type: 'textarea', maxLength: 2000 }), textField('answer_url', 'Link hồ sơ / bài đánh giá', { type: 'url', optional: true })]} submit="Gửi yêu cầu" reset onSubmit={async (values) => { await api.request('/me/role-requests', { method: 'POST', body: values }); roles.reload() }} />}
  </div></div>
    <div className="row"><h2>Phiên đăng nhập đang hoạt động</h2><button onClick={sessions.reload}>Làm mới</button></div>
    <Resource resource={sessions}>{(rows) => <div className="stack">{rows.map((row) => <article className="card card-body" key={row.id}>
      <h3>{row.is_current ? 'Phiên hiện tại' : 'Phiên khác'}</h3><p>Đăng nhập: {date(row.created_at)} · Hết hạn: {date(row.expires_at)}</p>
      <Action onClick={async () => { await api.request(`/auth/sessions/${row.id}/revoke`, { method: 'POST' }); if (row.is_current) onLogout(); else sessions.reload() }}>Thu hồi phiên</Action>
    </article>)}</div>}</Resource>
    <h2>Lịch sử nâng bậc</h2><Resource resource={roles} empty="Chưa có yêu cầu nâng bậc.">{(rows) => <div className="stack">{rows.map((row) => <article className="card card-body" key={row.id}><Details row={row} fields={['current_role_at_request', 'request_note', 'status', 'admin_note', 'created_at']} /></article>)}</div>}</Resource>
    <h2>Báo cáo của tôi</h2><Resource resource={reports} empty="Chưa có báo cáo.">{(rows) => <div className="stack">{rows.map((row) => <article className="card card-body" key={row.id}><Details row={row} fields={['reason_category', 'reason_details', 'status', 'created_at']} /></article>)}</div>}</Resource>
    {['tutor', 'admin', 'head_admin'].includes(user.role) && <><h2>Quyết toán gia sư</h2><Resource resource={settlements} empty="Chưa có quyết toán.">{(rows) => <div className="card-grid">{rows.map((row) => <article className="card card-body" key={row.id}><Details row={row} fields={['booking_id', 'total_amount', 'platform_fee', 'tutor_income', 'status', 'release_date']} /></article>)}</div>}</Resource></>}
  </section>
}
