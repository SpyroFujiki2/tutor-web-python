import { useRef, useState } from 'react'
import { labels, date, uuid } from './workspace-utils.js'
import Icon from './Icon.jsx'

export function Resource({ resource, children, empty = 'Chưa có dữ liệu.' }) {
  if (resource.loading) return <div role="status" aria-label="Đang tải nội dung" className="skeleton-grid">{[0, 1, 2].map((key) => <div className="skeleton-card" aria-hidden="true" key={key}><div className="skeleton skeleton-cover" /><div className="skeleton skeleton-title" /><div className="skeleton" /><div className="skeleton skeleton-short" /></div>)}<span className="sr-only">Đang tải nội dung…</span></div>
  if (resource.error) return <div role="alert" className="resource-error"><div><Icon name="alert" size={26} /><div><strong>Chưa tải được nội dung</strong><p>{resource.error}</p></div></div><button onClick={resource.reload}>Thử lại<Icon name="arrow" size={15} /></button></div>
  if (Array.isArray(resource.data) && !resource.data.length) return <div className="empty"><Icon name="folder" size={30} />{empty}</div>
  return resource.data ? children(resource.data) : null
}

export function Action({ children, onClick, className = '', disabled = false }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const lock = useRef(false)
  async function run() {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    setError('')
    try { await onClick() } catch (err) { setError(err.message) }
    finally { lock.current = false; setBusy(false) }
  }
  return <span className="action"><button className={className} disabled={busy || disabled} onClick={run}>{busy ? 'Đang xử lý…' : children}</button>{error && <span role="alert" className="error-text">{error}</span>}</span>
}

export function Form({ fields, onSubmit, submit = 'Lưu', initial = {}, reset = false }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const lock = useRef(false)
  const requestId = useRef(null)
  async function handle(event) {
    event.preventDefault()
    if (lock.current) return
    const form = event.currentTarget
    const raw = new FormData(form)
    const values = Object.fromEntries(fields.map((field) => {
      const value = raw.get(field.name)
      return [field.name, field.type === 'checkbox' ? raw.has(field.name) : field.type === 'number'
        ? value === '' && field.optional ? null : Number(value) : value === '' && field.optional ? null : value]
    }))
    requestId.current ??= uuid()
    lock.current = true
    setBusy(true); setError(''); setSuccess(false)
    try {
      await onSubmit(values, requestId.current)
      requestId.current = null
      setSuccess(true)
      if (reset) form.reset()
    } catch (err) { setError(err.message) }
    finally { lock.current = false; setBusy(false) }
  }
  return <form onSubmit={handle} className="form">
    <fieldset disabled={busy}>
      {fields.map((field) => <label key={field.name} className={field.type === 'checkbox' ? 'checkbox' : ''}>
        <span>{field.label}</span>
        {field.options ? <select name={field.name} defaultValue={initial[field.name] ?? field.default ?? ''} required={!field.optional}>
          <option value="" disabled>Chọn…</option>
          {field.options.map((option) => <option key={option.value ?? option} value={option.value ?? option}>{option.label ?? labels[option] ?? option}</option>)}
        </select> : field.type === 'textarea' ? <textarea name={field.name} defaultValue={initial[field.name] ?? ''} required={!field.optional} maxLength={field.maxLength ?? 20000} placeholder={field.placeholder} rows={4} />
          : <input name={field.name} type={field.type ?? 'text'} required={!field.optional && field.type !== 'checkbox'}
            defaultValue={field.type === 'checkbox' ? undefined : initial[field.name] ?? field.default ?? ''}
            defaultChecked={field.type === 'checkbox' ? initial[field.name] ?? field.default ?? false : undefined}
            min={field.min} max={field.max} step={field.step} minLength={field.minLength} maxLength={field.maxLength ?? 1024}
            autoComplete={field.autoComplete} placeholder={field.placeholder} />}
        {field.hint && <small>{field.hint}</small>}
      </label>)}
      <button className="primary" type="submit">{busy ? 'Đang xử lý…' : submit}</button>
    </fieldset>
    {error && <p role="alert" className="notice error">{error}</p>}
    {success && <p role="status" className="success">Đã lưu thành công.</p>}
  </form>
}

export function Badge({ value }) { return <span className={`badge badge-${value}`}>{labels[value] ?? value}</span> }
export function Pager({ offset, setOffset, length, size = 20, hasNext = length >= size, disabled = false }) {
  return <nav className="pager" aria-label="Phân trang"><button disabled={disabled || !offset} onClick={() => setOffset(Math.max(0, offset - size))}><Icon name="back" size={14} />Trước</button><span>Trang {Math.floor(offset / size) + 1}</span><button disabled={disabled || !hasNext} onClick={() => setOffset(offset + size)}>Tiếp<Icon name="arrow" size={14} /></button></nav>
}

const fieldLabels = {
  full_name: 'Họ và tên',
  price: 'Giá niêm yết', credits: 'Số credit', is_active: 'Đang mở bán', is_live: 'Học trực tiếp',
  id: 'Mã', subscription_id: 'Mã đăng ký', customer_id: 'Khách hàng', tutor_id: 'Gia sư',
  user_id: 'Người dùng', booking_id: 'Mã đơn học', course_id: 'Mã khóa học', admin_id: 'Người xử lý',
  title_at_purchase: 'Nội dung đăng ký', price_at_purchase: 'Giá lúc mua', status: 'Trạng thái', role: 'Vai trò',
  created_at: 'Ngày tạo', activated_at: 'Kích hoạt', expired_at: 'Hết hạn', updated_at: 'Cập nhật',
  starts_at: 'Bắt đầu', ends_at: 'Kết thúc', release_date: 'Hạn giải ngân', actual_released_at: 'Đã giải ngân lúc',
  amount: 'Số credit', amount_vnd: 'Số tiền (VND)', credit_amount: 'Số credit', order_type: 'Loại đơn', type: 'Loại',
  available_balance: 'Số dư', holding_balance: 'Tạm giữ', debt: 'Công nợ', commission_rate: 'Phí (%)',
  spendable_balance: 'Có thể chi', reserved_withdrawals: 'Giữ cho đơn rút', contract_id: 'Mã hợp đồng',
  total_amount: 'Tổng tiền', platform_fee: 'Phí nền tảng', tutor_income: 'Thu nhập gia sư', hold_amount: 'Tạm giữ ban đầu',
  available_amount: 'Khả dụng ban đầu', progress_percent: 'Tiến độ (%)', final_score: 'Điểm tổng kết', result: 'Kết quả',
  attendance_ratio: 'Tỷ lệ hoàn thành', midterm_score: 'Điểm giữa kỳ', endterm_score: 'Điểm cuối kỳ', practice_score: 'Điểm thực hành',
  current_role_at_request: 'Bậc hiện tại khi gửi', request_note: 'Nội dung yêu cầu', admin_note: 'Phản hồi',
  reason_category: 'Lý do', reason_details: 'Chi tiết', verdict: 'Kết luận', is_completed: 'Đã giải quyết',
  action_code: 'Thao tác', target_type: 'Đối tượng', reason: 'Ghi chú', email: 'Email', direction: 'Chiều giao dịch',
  balance_before: 'Số dư trước', balance_after: 'Số dư sau', snapshot_date: 'Ngày', balance_snap: 'Tổng số dư',
  available_snap: 'Khả dụng', holding_snap: 'Tạm giữ', is_hidden: 'Đã ẩn', min_role_level: 'Bậc đọc tối thiểu',
}
export function Details({ row, fields }) {
  return <dl className="details">{fields.filter((key) => row[key] !== null && row[key] !== undefined).map((key) => <div key={key}>
    <dt>{fieldLabels[key] ?? key}</dt><dd>{typeof row[key] === 'boolean' ? row[key] ? 'Có' : 'Không'
      : key.endsWith('_at') || ['starts_at', 'ends_at', 'release_date'].includes(key) ? date(row[key])
        : labels[row[key]] ?? String(row[key])}</dd>
  </div>)}</dl>
}

