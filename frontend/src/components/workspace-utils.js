import { useEffect, useState } from 'react'

export const labels = {
  pending: 'Chờ xử lý', confirmed: 'Đã thanh toán', assigned: 'Đã phân công', completed: 'Hoàn thành',
  cancelled: 'Đã hủy', refunded: 'Đã hoàn tiền', disputing: 'Đang tranh chấp', scheduled: 'Đã lên lịch',
  active: 'Hoạt động', expired: 'Hết hạn', success: 'Thành công', failed: 'Không đạt / thất bại',
  visible: 'Hiển thị', hidden: 'Đã ẩn', approved: 'Đã duyệt', rejected: 'Từ chối',
  held: 'Tạm giữ', released: 'Đã giải ngân', normal: 'Ví cá nhân', commercial: 'Ví gia sư',
  member: 'Thành viên', student: 'Học viên', trainee_tutor: 'Gia sư tập sự', tutor: 'Gia sư',
  admin: 'Quản trị viên', head_admin: 'Quản trị cấp cao', guest: 'Khách', suspended: 'Tạm khóa', banned: 'Đã khóa',
  course: 'Khóa học', booking: 'Gia sư', in: 'Nạp / nhận', out: 'Rút / chi', excellent: 'Xuất sắc', good: 'Đạt',
  refund_full: 'Hoàn toàn bộ', refund_partial: 'Hoàn một phần', payment: 'Thanh toán', revenue: 'Thu nhập', refund: 'Hoàn tiền',
}
export const money = (value) => new Intl.NumberFormat('vi-VN').format(value ?? 0)
export const date = (value) => value ? new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`).toLocaleString('vi-VN') : 'Chưa có'
export const uuid = () => crypto.randomUUID()
export const isAdmin = (user) => ['admin', 'head_admin'].includes(user?.role)

export function useResource(api, path, version = 0, pollMs = 0, keepPrevious = false) {
  const [state, setState] = useState({})
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    if (!path || !pollMs) return
    const timer = setInterval(() => {
      if (document.visibilityState !== 'hidden') setRevision((value) => value + 1)
    }, pollMs)
    return () => clearInterval(timer)
  }, [path, pollMs])
  useEffect(() => {
    if (!path) return
    const controller = new AbortController()
    api.request(path, { signal: controller.signal }).then(
      (data) => { if (!controller.signal.aborted) setState({ path, version, revision, data }) },
      (error) => { if (!controller.signal.aborted) setState({ path, version, revision, error: error.message }) },
    )
    return () => controller.abort()
  }, [api, path, version, revision])
  const current = state.path === path && state.version === version && state.revision === revision
  const usable = current || (pollMs > 0 && state.path === path && state.version === version && !!state.data)
  const retained = keepPrevious && !current && !!state.data
  return { data: usable || retained ? state.data : null, error: current ? state.error : null,
    loading: !!path && !retained && (!usable || (!state.data && !state.error)), refreshing: !!path && retained,
    reload: () => setRevision((value) => value + 1) }
}

export const textField = (name, label, extra = {}) => ({ name, label, ...extra })
export const numberField = (name, label, extra = {}) => ({ name, label, type: 'number', min: 0, max: 2147483647, ...extra })
export const reasonField = textField('reason', 'Lý do / tham chiếu đối soát', { maxLength: 200 })
export const sessionFields = [textField('starts_at', 'Bắt đầu', { type: 'datetime-local' }),
  textField('ends_at', 'Kết thúc', { type: 'datetime-local' }), textField('meeting_url', 'Link phòng học', { type: 'url', optional: true }),
  textField('location', 'Địa điểm', { optional: true }), textField('note', 'Ghi chú', { optional: true })]
export const sessionPayload = (value) => ({ ...value, starts_at: new Date(value.starts_at).toISOString(), ends_at: new Date(value.ends_at).toISOString() })
