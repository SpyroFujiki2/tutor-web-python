import DataTable from './DataTable.jsx'
import { Badge } from './Workspace.jsx'
import { date, labels, money } from './workspace-utils.js'
import { adminSections } from '../admin-navigation.js'

const definitions = {
  users: [['full_name', 'Họ và tên'], ['email', 'Email'], ['role', 'Vai trò', 'badge'], ['status', 'Trạng thái', 'badge']],
  courses: [['title', 'Khóa học'], ['price', 'Học phí (credit)', 'money'], ['is_live', 'Hình thức', 'course'], ['status', 'Trạng thái', 'badge'], ['created_at', 'Ngày tạo', 'date']],
  'tutoring-packages': [['name', 'Gói gia sư'], ['price', 'Học phí (credit)', 'money'], ['is_active', 'Trạng thái', 'active']],
  'credit-packages': [['name', 'Gói nạp'], ['credits', 'Số credit', 'money'], ['price', 'Giá (VND)', 'money'], ['is_active', 'Trạng thái', 'active']],
  bookings: [['subject', 'Môn học'], ['customer_id', 'Mã khách hàng', 'code'], ['tutor_id', 'Mã gia sư', 'code'], ['status', 'Trạng thái', 'badge'], ['created_at', 'Ngày tạo', 'date']],
  progress: [['subscription_id', 'Mã đăng ký', 'code'], ['progress_percent', 'Tiến độ (%)'], ['final_score', 'Điểm tổng kết'], ['result', 'Kết quả', 'badge'], ['updated_at', 'Cập nhật', 'date']],
  'role-requests': [['user_id', 'Mã người yêu cầu', 'code'], ['current_role_at_request', 'Bậc hiện tại', 'badge'], ['status', 'Trạng thái', 'badge'], ['created_at', 'Ngày gửi', 'date']],
  posts: [['title', 'Bài viết'], ['author_nickname', 'Tác giả'], ['is_hidden', 'Hiển thị', 'visibility'], ['created_at', 'Ngày đăng', 'date']],
  reports: [['reason_category', 'Lý do báo cáo'], ['status', 'Trạng thái', 'badge'], ['admin_id', 'Người xử lý', 'code'], ['created_at', 'Ngày gửi', 'date']],
  disputes: [['reason_category', 'Lý do tranh chấp'], ['booking_id', 'Mã đơn gia sư', 'code'], ['is_completed', 'Trạng thái', 'resolved'], ['verdict', 'Kết luận', 'badge'], ['created_at', 'Ngày tạo', 'date']],
  'cash-orders': [['order_type', 'Loại đơn', 'badge'], ['amount_vnd', 'Số tiền (VND)', 'money'], ['credit_amount', 'Số credit', 'money'], ['provider', 'Thanh toán', 'provider'], ['status', 'Trạng thái', 'badge'], ['created_at', 'Ngày tạo', 'date']],
  settlements: [['booking_id', 'Mã đơn gia sư', 'code'], ['total_amount', 'Tổng credit', 'money'], ['platform_fee', 'Phí nền tảng', 'money'], ['tutor_income', 'Thu nhập gia sư', 'money'], ['status', 'Trạng thái', 'badge'], ['release_date', 'Hạn giải ngân', 'date']],
}

function cell(row, key, type) {
  const value = row[key]
  if (key === 'full_name' && !value) return <span className="muted">Chưa cập nhật</span>
  if (type === 'provider') return value === 'vnpay' ? 'VNPAY' : 'Chuyển khoản'
  if (value == null || value === '') return '—'
  if (type === 'badge') return <Badge value={value} />
  if (type === 'money') return money(value)
  if (type === 'date') return date(value)
  if (type === 'code') return <code className="table-reference">{value}</code>
  if (type === 'active') return <Badge value={value ? 'active' : 'hidden'} />
  if (type === 'visibility') return value ? 'Đã ẩn' : 'Đang hiển thị'
  if (type === 'resolved') return value ? 'Đã giải quyết' : 'Đang xử lý'
  if (type === 'course') return value ? 'Trực tiếp' : 'Video'
  return Object.hasOwn(labels, value) ? labels[value] : String(value)
}

export default function AdminTable({ section, rows, onSelect }) {
  const columns = (definitions[section] ?? [['id', 'Mã', 'code'], ['status', 'Trạng thái', 'badge']]).map(([key, label, type]) => ({ key, label, render: (row) => cell(row, key, type) }))
  columns.push({ key: 'actions', label: 'Chi tiết', render: (row) => <button className="table-action" onClick={() => onSelect(row)}>Xem chi tiết</button> })
  return <DataTable label={adminSections.find((item) => item.id === section)?.label ?? 'Dữ liệu quản trị'} columns={columns} rows={rows} />
}
