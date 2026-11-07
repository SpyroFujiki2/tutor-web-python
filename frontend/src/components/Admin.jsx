import ExternalContent from './ExternalContent.jsx'
import { useState } from 'react'
import { Action, Badge, Details, Form, Pager, Resource } from './Workspace.jsx'
import { numberField, reasonField, sessionFields, sessionPayload, textField, useResource } from './workspace-utils.js'
import { Chat } from './Tutoring.jsx'
import FinanceAdmin from './FinanceAdmin.jsx'
import { adminGroups, adminSections, resolveAdminSection } from '../admin-navigation.js'
import { useLocation } from '../navigation.js'
import Icon from './Icon.jsx'
import { labels } from './workspace-utils.js'

const catalogFields = {
  courses: [textField('title', 'Tên khóa học', { maxLength: 200 }), textField('description', 'Mô tả', { type: 'textarea', optional: true }), numberField('price', 'Giá (credit)'), { name: 'is_live', label: 'Khóa học trực tiếp', type: 'checkbox' }, { name: 'status', label: 'Hiển thị', options: ['visible', 'hidden'], default: 'visible' }],
  'tutoring-packages': [textField('name', 'Tên gói', { maxLength: 200 }), numberField('price', 'Giá (credit)'), { name: 'is_active', label: 'Mở bán', type: 'checkbox', default: true }],
  'credit-packages': [textField('name', 'Tên gói', { maxLength: 200 }), numberField('credits', 'Số credit', { min: 1 }), numberField('price', 'Giá (VND)', { min: 1 }), { name: 'is_active', label: 'Mở bán', type: 'checkbox', default: true }],
}
const lessonFields = [numberField('order_idx', 'Thứ tự', { min: 1, max: 10000 }), textField('media_url', 'URL nội dung', { type: 'url', optional: true }), textField('assignment_url', 'URL bài tập', { type: 'url', optional: true }), numberField('duration_minutes', 'Thời lượng (phút)', { min: 1, max: 10000, optional: true }), numberField('session_count', 'Số buổi', { min: 1, max: 1000, optional: true })]
const rowFields = ['id', 'subscription_id', 'email', 'role', 'status', 'price', 'credits', 'is_active', 'is_live', 'customer_id', 'tutor_id', 'booking_id', 'course_id', 'user_id', 'admin_id', 'title_at_purchase', 'order_type', 'amount_vnd', 'credit_amount', 'current_role_at_request', 'request_note', 'admin_note', 'reason_details', 'is_completed', 'verdict', 'total_amount', 'platform_fee', 'tutor_income', 'release_date', 'actual_released_at', 'progress_percent', 'final_score', 'result', 'action_code', 'target_type', 'reason', 'is_hidden', 'created_at']

export default function Admin({ api, user }) {
  const location = useLocation()
  const current = resolveAdminSection(location)
  const group = adminGroups.find((group) => group.items.some((item) => item.id === current.id))
  return <section className="admin-page"><div className="admin-welcome"><div><p className="eyebrow"><span className="online-dot" />KHÔNG GIAN VẬN HÀNH</p><h1>Quản trị, gọn trong tầm tay.</h1><p>Quản lý hoạt động đào tạo, thành viên và tài chính trong một không gian.</p></div><div className="admin-identity"><span className="admin-identity-icon"><Icon name="shield" size={27} /></span><div><strong>{labels[user.role]}</strong><small>{user.email}</small></div></div></div><div className="admin-breadcrumb"><span>Quản trị</span><Icon name="arrow" size={12} /><span>{group.label}</span><Icon name="arrow" size={12} /><strong>{current.label}</strong></div>{current.id === 'finance' ? <FinanceAdmin api={api} user={user} /> : <AdminList key={current.id} api={api} user={user} section={current.id} />}</section>
}

function AdminList({ api, user, section }) {
  const [offset, setOffset] = useState(0)
  const resource = useResource(api, `/admin/${section}?limit=20&offset=${offset}`)
  async function mutate(path, body, method = 'POST') {
    const result = await api.request(path, { method, ...(body === undefined ? {} : { body }) })
    resource.reload()
    return result
  }
  const fields = catalogFields[section]
  const current = adminSections.find((item) => item.id === section)
  const catalogPayload = (values) => ({ ...values, ...(section === 'courses' ? { description: values.description ?? '' } : {}) })
  return <>
    <div className="admin-section-heading"><div><h2>{current.label}</h2><p>{current.description}</p></div><div className="actions"><button onClick={resource.reload}><Icon name="refresh" size={16} />Làm mới</button>{section === 'action-logs' && <><Action onClick={() => mutate('/admin/jobs/snapshots')}>Chụp số dư hôm nay</Action><Action onClick={() => mutate('/admin/jobs/expire-subscriptions')}>Cập nhật quyền hết hạn</Action></>}</div></div>
    {section === 'cash-orders' && <div className="notice payment-policy"><Icon name="shield" size={21} /><div><strong>VNPAY xác nhận tự động</strong><p>Thanh toán VNPAY thành công sẽ tự cộng credit vào ví. Quản trị chỉ đối soát đơn chuyển khoản thủ công và yêu cầu rút tiền.</p></div></div>}
    {fields && <details className="card card-body create-record"><summary><Icon name="plus" size={18} />Tạo mới {current.label.toLocaleLowerCase('vi')}</summary><Form fields={fields} reset onSubmit={(values) => mutate(`/admin/${section}`, catalogPayload(values))} /></details>}
    <Resource resource={resource}>{(rows) => <><div className="stack admin-records">{rows.map((row) => <article className="card card-body admin-record" key={row.id ?? row.subscription_id}>
      <div className="row"><h2>{row.title ?? row.name ?? row.subject ?? row.reason_category ?? row.email ?? current.label}</h2>{row.status && <Badge value={row.status} />}</div><Details row={row} fields={rowFields.filter((key) => key !== 'id' && !key.endsWith('_id'))} />
      {rowFields.some((key) => (key === 'id' || key.endsWith('_id')) && row[key]) && <details className="reference-details"><summary>Mã tham chiếu</summary><Details row={row} fields={rowFields.filter((key) => key === 'id' || key.endsWith('_id'))} /></details>}
      {row.content && <p className="preserve">{row.content}</p>}{row.answer_url && <ExternalContent url={row.answer_url} title="Xem hồ sơ" />}
      {fields && <details><summary>Chỉnh sửa</summary><Form fields={fields} initial={row} onSubmit={(values) => mutate(`/admin/${section}/${row.id}`, catalogPayload(values), 'PUT')} /></details>}
      {section === 'courses' && <LessonEditor api={api} course={row} />}
      {section === 'users' && row.id !== user.id && <details><summary>Thay đổi trạng thái</summary><Form fields={[{ name: 'status', label: 'Trạng thái', options: ['active', 'suspended', 'banned'] }, reasonField]} onSubmit={(values) => mutate(`/admin/users/${row.id}/status`, values)} /></details>}
      {section === 'bookings' && <BookingAdmin api={api} row={row} mutate={mutate} />}
      {section === 'cash-orders' && row.provider === 'vnpay' && <p className={`payment-state ${row.status === 'success' ? 'is-success' : ''}`}><Icon name={row.status === 'success' ? 'check' : 'clock'} size={17} />{row.status === 'success' ? 'Đã ghi nhận thanh toán · Credit đã được cộng vào ví.' : row.status === 'pending' ? 'Đang chờ VNPAY xác nhận · Không cần quản trị duyệt.' : 'Đơn VNPAY được cập nhật tự động theo kết quả thanh toán.'}</p>}
      {section === 'cash-orders' && row.provider !== 'vnpay' && user.role === 'head_admin' && row.status === 'pending' && <>{row.order_type === 'out' && <BankDetails api={api} id={row.id} />}<details><summary>Xác nhận sau đối soát</summary><p>Chỉ xác nhận sau khi tiền đã thực nhận hoặc chuyển đi. Ghi tham chiếu chứng từ trong lý do.</p><Form fields={[{ name: 'success', label: 'Kết quả', options: [{ value: 'true', label: 'Thành công' }, { value: 'false', label: 'Thất bại' }] }, reasonField]} onSubmit={(values) => mutate(`/admin/cash-orders/${row.id}/decision`, { ...values, success: values.success === 'true' })} /></details></>}
      {section === 'role-requests' && row.status === 'pending' && <Decision onSubmit={(values) => mutate(`/admin/role-requests/${row.id}/decision`, values)} />}
      {section === 'reports' && row.status === 'pending' && <>{!row.admin_id && <Action onClick={() => mutate(`/admin/reports/${row.id}/claim`)}>Nhận xử lý</Action>}{row.admin_id === user.id && <><ReportContext api={api} id={row.id} /><Decision onSubmit={(values) => mutate(`/admin/reports/${row.id}/decision`, values)} /></>}</>}
      {section === 'disputes' && <>{!row.is_completed && !row.admin_id && <Action onClick={() => mutate(`/admin/disputes/${row.id}/claim`)}>Nhận xử lý</Action>}{row.admin_id === user.id && <><Chat api={api} user={user} bookingId={row.booking_id} disputeId={row.id} closed={row.is_completed} />{!row.is_completed && <details><summary>Giải quyết tranh chấp</summary><Form fields={[{ name: 'verdict', label: 'Kết luận', options: ['rejected', 'refund_full', 'refund_partial'] }, numberField('refund_amount', 'Credit hoàn nếu hoàn một phần', { default: 0 }), reasonField]} onSubmit={(values) => mutate(`/admin/disputes/${row.id}/decision`, values)} /></details>}</>}</>}
      {section === 'settlements' && row.status === 'held' && <Action onClick={() => mutate(`/admin/settlements/${row.id}/release`)}>Giải ngân khi đến hạn</Action>}
      {section === 'settlements' && row.status === 'released' && user.role === 'head_admin' && <details><summary>Hoàn credit sau giải ngân</summary><p>Hoàn toàn bộ credit cho khách hàng, thu hồi phần thu nhập gia sư và ghi công nợ nếu cần. Ví nền tảng phải đủ thanh khoản.</p><Form fields={[reasonField]} submit="Xác nhận hoàn toàn bộ" onSubmit={(values) => mutate(`/admin/bookings/${row.booking_id}/refund-released`, values)} /></details>}
      {section === 'progress' && <><ProgressAdmin api={api} row={row} mutate={mutate} /><details><summary>Hoàn toàn bộ học phí và hủy quyền học</summary><Form fields={[reasonField]} submit="Xác nhận hoàn tiền" onSubmit={(values) => mutate(`/admin/subscriptions/${row.subscription_id}/refund`, values)} /></details></>}
      {section === 'posts' && <Action onClick={() => mutate(`/posts/${row.id}/visibility`, { is_hidden: !row.is_hidden, reason: 'Quản trị nội dung' })}>{row.is_hidden ? 'Hiện bài viết' : 'Ẩn bài viết'}</Action>}
    </article>)}</div><Pager offset={offset} setOffset={setOffset} length={rows.length} /></>}</Resource>
  </>
}

function Decision({ onSubmit }) {
  return <details><summary>Duyệt / từ chối</summary><Form fields={[{ name: 'approve', label: 'Quyết định', options: [{ value: 'true', label: 'Duyệt' }, { value: 'false', label: 'Từ chối' }] }, reasonField]} onSubmit={(values) => onSubmit({ ...values, approve: values.approve === 'true' })} /></details>
}

function LessonEditor({ api, course }) {
  const [open, setOpen] = useState(false)
  const resource = useResource(api, open ? `/admin/courses/${course.id}/lessons` : null)
  const base = `/admin/courses/${course.id}/lessons`
  async function reorder(rows, index, direction) {
    const ids = rows.map((row) => row.id)
    const temporary = ids[index]
    ids[index] = ids[index + direction]
    ids[index + direction] = temporary
    await api.request(`/admin/courses/${course.id}/reorder`, { method: 'POST', body: { lesson_ids: ids } }); resource.reload()
  }
  return <details onToggle={(event) => setOpen(event.currentTarget.open)}><summary>Quản lý bài học</summary><p className="muted">Khóa đã có học viên chỉ cho đổi thứ tự bài. Nội dung và thời lượng được giữ để bảo toàn lịch sử học.</p><Resource resource={resource} empty="Chưa có bài học.">{(rows) => <div className="stack">{rows.map((row, index) => <div key={row.id} className="inset"><h3>Bài {row.order_idx}</h3><div className="actions"><Action disabled={index === 0} onClick={() => reorder(rows, index, -1)}>↑</Action><Action disabled={index === rows.length - 1} onClick={() => reorder(rows, index, 1)}>↓</Action><Action onClick={async () => { await api.request(`${base}/${row.id}`, { method: 'DELETE' }); resource.reload() }}>Xóa bài</Action></div><Form fields={lessonFields} initial={row} onSubmit={async (values) => { await api.request(`${base}/${row.id}`, { method: 'PUT', body: values }); resource.reload() }} /></div>)}</div>}</Resource><h3>Thêm bài học</h3><Form fields={lessonFields} reset onSubmit={async (values) => { await api.request(base, { method: 'POST', body: values }); resource.reload() }} /></details>
}

function BookingAdmin({ api, row, mutate }) {
  const tutors = useResource(api, ['confirmed', 'assigned'].includes(row.status) ? '/admin/users?role=tutor&limit=100' : null)
  const [open, setOpen] = useState(false)
  const sessions = useResource(api, open ? `/bookings/${row.id}/sessions` : null)
  return <>{tutors.data && <Form fields={[{ name: 'tutor_id', label: 'Phân công gia sư (cần có ví gia sư)', options: tutors.data.filter((user) => user.status === 'active').map((user) => ({ value: user.id, label: user.email })) }]} onSubmit={(values) => mutate(`/admin/bookings/${row.id}/assign`, values)} />}<details onToggle={(event) => setOpen(event.currentTarget.open)}><summary>Lịch học</summary><Resource resource={sessions}>{(rows) => <div className="stack">{rows.map((item) => <div className="inset" key={item.id}><h3>Buổi {item.session_no}</h3><Details row={item} fields={['starts_at', 'ends_at', 'status']} />{row.status === 'assigned' && item.status === 'scheduled' && <><Form fields={sessionFields} onSubmit={async (values) => { await mutate(`/bookings/${row.id}/sessions/${item.id}`, sessionPayload(values), 'PUT'); sessions.reload() }} /><Action onClick={async () => { await mutate(`/bookings/${row.id}/sessions/${item.id}/action`, { action: 'complete' }); sessions.reload() }}>Hoàn tất buổi</Action></>}</div>)}</div>}</Resource></details>{row.status === 'assigned' && <Action onClick={() => mutate(`/bookings/${row.id}/complete`)}>Xác nhận hoàn thành đơn</Action>}</>
}

function BankDetails({ api, id }) {
  const [details, setDetails] = useState(null)
  return <><Action onClick={async () => setDetails(await api.request(`/admin/cash-orders/${id}/bank-details`))}>Xem tài khoản nhận tiền</Action>{details && <div className="inset"><p>{details.bank_name} · {details.account_number}</p><p>{details.account_holder_name}</p><button onClick={() => setDetails(null)}>Đóng thông tin</button></div>}</>
}

function ProgressAdmin({ api, row, mutate }) {
  const [open, setOpen] = useState(false)
  const lessons = useResource(api, open ? `/admin/courses/${row.course_id}/lessons` : null)
  return <details onToggle={(event) => setOpen(event.currentTarget.open)}><summary>Điểm danh & chấm điểm</summary><Form fields={[numberField('midterm_score', 'Giữa kỳ', { max: 100 }), numberField('endterm_score', 'Cuối kỳ', { max: 100 }), numberField('practice_score', 'Thực hành', { max: 100 })]} initial={row} onSubmit={(values) => mutate(`/admin/subscriptions/${row.subscription_id}/grade`, values)} /><Resource resource={lessons}>{(items) => <ul className="plain-list">{items.map((item) => <li key={item.id}>Bài {item.order_idx} <Action onClick={() => mutate(`/admin/subscriptions/${row.subscription_id}/lessons/${item.id}/attendance`, { is_absent: false })}>Có mặt (lớp trực tiếp)</Action><Action onClick={() => mutate(`/admin/subscriptions/${row.subscription_id}/lessons/${item.id}/attendance`, { is_absent: true })}>Vắng</Action></li>)}</ul>}</Resource></details>
}

function ReportContext({ api, id }) {
  const resource = useResource(api, `/admin/reports/${id}/context`)
  return <Resource resource={resource}>{(data) => <div className="inset"><h3>{data.post.title}</h3><p className="preserve">{data.post.content}</p><h4>Bình luận bị báo cáo</h4><p className="preserve">{data.comment.content}</p></div>}</Resource>
}
