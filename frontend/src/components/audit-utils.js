import { labels } from './workspace-utils.js'

const fields = {
  role: 'Vai trò', status: 'Trạng thái', revoked_sessions: 'Số phiên đã thu hồi',
  title: 'Tên khóa học', price: 'Giá', is_live: 'Học trực tiếp', lesson_ids: 'Thứ tự bài học',
  order_idx: 'Thứ tự bài học', is_hidden: 'Ẩn nội dung', min_role_level: 'Bậc đọc tối thiểu',
  tutor_id: 'Mã gia sư', starts_at: 'Bắt đầu', ends_at: 'Kết thúc', verdict: 'Kết luận',
  refund_amount: 'Số credit hoàn', midterm_score: 'Điểm giữa kỳ', endterm_score: 'Điểm cuối kỳ',
  practice_score: 'Điểm thực hành', lesson_id: 'Mã bài học', is_absent: 'Vắng mặt',
  amount: 'Số credit', name: 'Tên', is_active: 'Đang hoạt động', credits: 'Số credit',
  commission_rate: 'Phí (%)', contract_id: 'Mã hợp đồng', debt: 'Công nợ', transaction_id: 'Mã giao dịch',
  recovered_amount: 'Số credit thu hồi', provider: 'Cổng thanh toán', transaction_no: 'Mã giao dịch thanh toán',
  assignment_completed: 'Bài tập đã được xác nhận hoàn thành',
}

export function auditValue(value, exists = true) {
  if (!exists) return 'Chưa có'
  if (value == null) return '—'
  if (typeof value === 'boolean') return value ? 'Có' : 'Không'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return Object.hasOwn(labels, value) ? labels[value] : String(value)
}

export function auditChanges(before, after) {
  const oldData = before && typeof before === 'object' && !Array.isArray(before) ? before : {}
  const newData = after && typeof after === 'object' && !Array.isArray(after) ? after : {}
  return [...new Set([...Object.keys(oldData), ...Object.keys(newData)])].map((key) => ({
    key, label: Object.hasOwn(fields, key) ? fields[key] : key,
    before: auditValue(oldData[key], Object.hasOwn(oldData, key)),
    after: auditValue(newData[key], Object.hasOwn(newData, key)),
    changed: Object.hasOwn(oldData, key) !== Object.hasOwn(newData, key) || JSON.stringify(oldData[key]) !== JSON.stringify(newData[key]),
  }))
}
