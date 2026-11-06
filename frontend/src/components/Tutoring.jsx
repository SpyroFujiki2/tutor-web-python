import { useState } from 'react'
import { Action, Badge, Details, Form, Pager, Resource } from './Workspace.jsx'
import { date, isAdmin, money, sessionFields, sessionPayload, textField, useResource } from './workspace-utils.js'
import { useCollection } from './use-collection.js'
import { filterCollection } from './collection-utils.js'
import CollectionToolbar from './CollectionToolbar.jsx'
import ContentDialog from './ContentDialog.jsx'
import Icon from './Icon.jsx'

export function Tutoring({ api, user, onLogin }) {
  const [selected, setSelected] = useState(null)
  const [chosenPackage, setChosenPackage] = useState(null)
  const [query, setQuery] = useState('')
  const [price, setPrice] = useState('all')
  const [sort, setSort] = useState('price_asc')
  const [packageOffset, setPackageOffset] = useState(0)
  const [offset, setOffset] = useState(0)
  const packages = useCollection(api, '/tutoring-packages')
  const bookings = useResource(api, user ? `/bookings?limit=20&offset=${offset}` : null)
  const rows = filterCollection(packages.data ?? [], { query, price, sort })
  const change = (setter) => (value) => { setter(value); setPackageOffset(0) }
  const reset = () => { setQuery(''); setPrice('all'); setSort('price_asc'); setPackageOffset(0) }
  if (selected && user) return <BookingRoom key={selected} api={api} user={user} id={selected} onBack={() => { setSelected(null); bookings.reload() }} />
  return <section className="tutoring-page"><div className="section-heading"><div><p className="eyebrow">CÓ NGƯỜI ĐỒNG HÀNH, TIẾN XA HƠN</p><h1>Tìm gói gia sư phù hợp</h1><p className="section-description">Chọn gói học, chia sẻ mục tiêu và cùng gia sư xây dựng từng bước tiến.</p></div><span className="section-icon"><Icon name="users" size={29} /></span></div>
    <CollectionToolbar query={query} onQueryChange={change(setQuery)} placeholder="Tìm gói gia sư bạn quan tâm…" count={packages.data ? rows.length : null} noun="gói gia sư" active={query || price !== 'all' || sort !== 'price_asc'} onReset={reset} filters={[
      { label: 'Học phí gói gia sư', value: price, onChange: change(setPrice), options: [['all', 'Mọi mức giá'], ['under500', 'Dưới 500 credit'], ['500to1000', '500 – 1.000 credit'], ['over1000', 'Trên 1.000 credit']] },
      { label: 'Sắp xếp gói gia sư', value: sort, onChange: change(setSort), options: [['price_asc', 'Giá tăng dần'], ['price_desc', 'Giá giảm dần'], ['name', 'Tên A → Z']] },
    ]} />
    <Resource resource={packages} empty="Gói gia sư mới đang được chuẩn bị. Hãy quay lại sau nhé.">{() => <>
      {rows.length ? <div className="card-grid">{rows.slice(packageOffset, packageOffset + 9).map((row) => <article className="card card-body tutor-card selectable-card" key={row.id}>
        <div className="row"><span className="package-icon"><Icon name="users" size={28} /></span><span className="badge badge-active">Đang nhận học viên</span></div><span className="eyebrow">HỌC CÙNG NGƯỜI HƯỚNG DẪN</span><h2>{row.name}</h2><p>Chia sẻ môn học và mục tiêu của bạn. Gia sư sẽ được phân công sau khi yêu cầu được thanh toán.</p><div className="course-meta"><Icon name="calendar" size={15} />Lịch học theo thỏa thuận</div><div className="card-bottom"><strong className="course-price">{money(row.price)}<small>credit</small></strong><button className="card-link" onClick={() => setChosenPackage(row)}>Xem gói học<Icon name="arrow" size={15} /></button></div>
      </article>)}</div> : <div className="empty"><Icon name="search" size={30} /><p>Chưa tìm thấy gói gia sư phù hợp.</p><button onClick={reset}>Xóa bộ lọc</button></div>}
      {rows.length > 9 && <Pager offset={packageOffset} setOffset={setPackageOffset} length={Math.min(9, rows.length - packageOffset)} size={9} hasNext={packageOffset + 9 < rows.length} />}
    </>}</Resource>
    {chosenPackage && <ContentDialog title="GÓI GIA SƯ ĐỒNG HÀNH" onClose={() => setChosenPackage(null)}><div className="section-icon"><Icon name="users" size={28} /></div><h2>{chosenPackage.name}</h2><p className="course-price"><strong>{money(chosenPackage.price)}</strong><small>credit</small></p><p className="dialog-description">Bắt đầu với một yêu cầu học. Sau khi thanh toán từ ví, quản trị sẽ phân công gia sư và hai bên thống nhất lịch học.</p><ul className="package-benefits"><li><Icon name="check" size={16} />Chọn môn học và mục tiêu của riêng bạn</li><li><Icon name="check" size={16} />Quản lý lịch học trong cùng một không gian</li><li><Icon name="check" size={16} />Trao đổi và gửi tài liệu cho gia sư</li></ul>{user ? <><h3>Chia sẻ mục tiêu của bạn</h3><Form fields={[textField('subject', 'Môn học', { maxLength: 200, placeholder: 'Ví dụ: Python cơ bản' }), textField('requirements', 'Mục tiêu & yêu cầu', { type: 'textarea', optional: true, maxLength: 5000, placeholder: 'Bạn muốn cải thiện điều gì?' })]} submit="Tạo yêu cầu học" onSubmit={async (values, requestId) => {
      const booking = await api.request('/bookings', { method: 'POST', body: { ...values, requirements: values.requirements ?? '', package_id: chosenPackage.id, request_id: requestId, sessions: [{}] } })
      setChosenPackage(null); setSelected(booking.id)
    }} /></> : <button className="primary" onClick={onLogin}>Đăng nhập để đặt gia sư<Icon name="arrow" size={17} /></button>}</ContentDialog>}
    {user && <div className="booking-section"><div className="section-heading"><div><p className="eyebrow">ĐỒNG HÀNH MỖI NGÀY</p><h2>Các đơn học của bạn</h2><p className="section-description">Theo dõi lịch học và tiếp tục trao đổi với gia sư.</p></div></div><Resource resource={bookings} empty="Bạn chưa có đơn học. Chọn một gói ở trên để bắt đầu.">{(items) => <><div className="card-grid">{items.map((row) => <article className="card card-body selectable-card" key={row.id}><div className="row"><h3>{row.subject}</h3><Badge value={row.status} /></div><p className="content-preview">{row.requirements || 'Mục tiêu học tập đang chờ được cập nhật.'}</p><p className="muted">{date(row.created_at)}</p><button className="card-link" onClick={() => setSelected(row.id)}>Lịch học & trao đổi<Icon name="arrow" size={16} /></button></article>)}</div><Pager offset={offset} setOffset={setOffset} length={items.length} /></>}</Resource></div>}
  </section>
}

export function BookingRoom({ api, user, id, onBack }) {
  const [version, setVersion] = useState(0)
  const booking = useResource(api, `/bookings/${id}`, version)
  const sessions = useResource(api, `/bookings/${id}/sessions`, version)
  const [editing, setEditing] = useState(null)
  const refresh = () => setVersion((value) => value + 1)
  return <section><button onClick={onBack}>← Danh sách đơn</button>
    <Resource resource={booking}>{(row) => <><div className="section-heading"><h1>{row.subject}</h1><Badge value={row.status} /></div><p className="preserve">{row.requirements}</p>
      <Details row={row} fields={['id', 'tutor_id', 'created_at']} />
      <div className="actions">
        {row.customer_id === user.id && row.status === 'pending' && <Action className="primary" onClick={async () => { await api.request(`/bookings/${id}/pay`, { method: 'POST' }); refresh() }}>Thanh toán bằng ví</Action>}
        {row.customer_id === user.id && ['pending', 'confirmed'].includes(row.status) && <Action onClick={async () => { await api.request(`/bookings/${id}/cancel`, { method: 'POST' }); refresh() }}>Hủy đơn / hoàn tiền</Action>}
        {row.customer_id === user.id && row.status === 'assigned' && <Action onClick={async () => { await api.request(`/bookings/${id}/complete`, { method: 'POST' }); refresh() }}>Xác nhận hoàn tất khóa gia sư</Action>}
      </div>
      <h2>Lịch học</h2><Resource resource={sessions}>{(items) => <div className="stack">{items.map((item) => <article className="card card-body" key={item.id}>
        <div className="row"><h3>Buổi {item.session_no}</h3><Badge value={item.status} /></div><Details row={item} fields={['starts_at', 'ends_at']} />
        {item.meeting_url && <a className="button" href={item.meeting_url} target="_blank" rel="noreferrer">Vào phòng học ↗</a>}<p>{item.location}</p><p>{item.note}</p>
        {(row.tutor_id === user.id || isAdmin(user)) && row.status === 'assigned' && item.status === 'scheduled' && <div className="actions">
          <button onClick={() => setEditing(item.id)}>Xếp lại lịch</button>
          <Action onClick={async () => { await api.request(`/bookings/${id}/sessions/${item.id}/action`, { method: 'POST', body: { action: 'complete' } }); refresh() }}>Hoàn tất buổi</Action>
          <Action onClick={async () => { await api.request(`/bookings/${id}/sessions/${item.id}/action`, { method: 'POST', body: { action: 'cancel' } }); refresh() }}>Hủy buổi</Action>
        </div>}
      </article>)}</div>}</Resource>
      {(row.tutor_id === user.id || isAdmin(user)) && row.status === 'assigned' && <details open={!!editing}><summary>{editing ? 'Xếp lại lịch học' : 'Thêm buổi học'}</summary>
        <Form key={editing ?? 'new'} fields={sessionFields} onSubmit={async (values) => {
          await api.request(`/bookings/${id}/sessions${editing ? `/${editing}` : ''}`, { method: editing ? 'PUT' : 'POST', body: sessionPayload(values) }); setEditing(null); refresh()
        }} />{editing && <button onClick={() => setEditing(null)}>Hủy chỉnh sửa</button>}</details>}
      <Chat api={api} bookingId={id} user={user} closed={['cancelled', 'refunded'].includes(row.status)} />
      {['confirmed', 'assigned', 'completed'].includes(row.status) && <details><summary>Mở tranh chấp</summary><p>Trình bày vấn đề để quản trị xem xét trước khi giải ngân.</p>
        <Form fields={[textField('reason_category', 'Lý do', { maxLength: 200 })]} submit="Gửi tranh chấp" onSubmit={async (values) => { await api.request(`/bookings/${id}/dispute`, { method: 'POST', body: values }); refresh() }} /></details>}
    </>}</Resource>
  </section>
}

export function Chat({ api, bookingId, disputeId, user, closed = false }) {
  const [offset, setOffset] = useState(0)
  const suffix = disputeId ? `&dispute_id=${disputeId}` : ''
  const resource = useResource(api, `/bookings/${bookingId}/messages?limit=20&offset=${offset}${suffix}`, 0, closed ? 0 : 5000)
  return <div className="card card-body chat"><div className="row"><h2>{disputeId ? 'Trao đổi tranh chấp' : 'Trao đổi với gia sư'}</h2><button onClick={resource.reload}>Làm mới</button></div>
    <Resource resource={resource} empty="Chưa có tin nhắn.">{(rows) => <><ol className="messages">{[...rows].reverse().map((row) => <li key={row.id} className={row.sender_id === user.id ? 'mine' : ''}>
      <small>{row.sender_id === user.id ? 'Bạn' : `Thành viên ${row.sender_id.slice(0, 8)}`} · {date(row.created_at)}</small><p className="preserve">{row.content}</p>
      {row.file_url && <Action onClick={async () => {
        const blob = await api.request(row.file_url.replace(/^\/api/, ''), { responseType: 'blob' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url; link.download = row.file_url.split('/').at(-1); link.click()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      }}>Tải tệp đính kèm</Action>}
    </li>)}</ol><Pager offset={offset} setOffset={setOffset} length={rows.length} /></>}</Resource>
    {!closed && <Form fields={[textField('content', 'Tin nhắn', { type: 'textarea', maxLength: 5000 })]} submit="Gửi tin nhắn" reset onSubmit={async (values) => {
      await api.request(`/bookings/${bookingId}/messages${disputeId ? `?dispute_id=${disputeId}` : ''}`, { method: 'POST', body: values }); setOffset(0); resource.reload()
    }} />}
    {!closed && <AttachmentUpload api={api} bookingId={bookingId} disputeId={disputeId} onSent={resource.reload} />}
  </div>
}

function AttachmentUpload({ api, bookingId, disputeId, onSent }) {
  const [file, setFile] = useState(null)
  return <details><summary>Gửi tệp đính kèm</summary><p className="muted">PDF, PNG, JPEG hoặc văn bản UTF-8, tối đa 5 MB.</p>
    <label>Chọn tệp<input type="file" accept="application/pdf,image/png,image/jpeg,text/plain" onChange={(event) => setFile(event.target.files[0] ?? null)} /></label>
    <Action disabled={!file} onClick={async () => {
      if (file.size > 5 * 1024 * 1024) throw new Error('Tệp vượt giới hạn 5 MB.')
      const query = new URLSearchParams({ name: file.name })
      if (disputeId) query.set('dispute_id', disputeId)
      await api.request(`/bookings/${bookingId}/attachments?${query}`, { method: 'POST', rawBody: file, contentType: file.type })
      setFile(null); onSent()
    }}>Gửi tệp</Action>
  </details>
}

export function Disputes({ api, user }) {
  const resource = useResource(api, '/disputes?limit=100')
  return <section><h1>Tranh chấp của tôi</h1><Resource resource={resource} empty="Bạn không có tranh chấp.">{(rows) => <div className="stack">{rows.map((row) => <article key={row.id} className="card card-body">
    <h2>{row.reason_category}</h2><Details row={row} fields={['booking_id', 'is_completed', 'verdict', 'created_at']} />
    <Chat api={api} bookingId={row.booking_id} disputeId={row.id} user={user} closed={row.is_completed} />
  </article>)}</div>}</Resource></section>
}
