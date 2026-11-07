export const adminGroups = [
  { id: 'learning', label: 'Đào tạo', icon: 'book', items: [
    { id: 'courses', label: 'Khóa học', description: 'Nội dung khóa học và bài giảng', icon: 'video' },
    { id: 'tutoring-packages', label: 'Gói gia sư', description: 'Danh mục và học phí gia sư', icon: 'cap' },
    { id: 'bookings', label: 'Đơn gia sư', description: 'Phân công và theo dõi lịch học', icon: 'calendar' },
    { id: 'progress', label: 'Kết quả học tập', description: 'Điểm danh và đánh giá kết quả', icon: 'chart' },
  ] },
  { id: 'members', label: 'Thành viên', icon: 'users', items: [
    { id: 'users', label: 'Người dùng', description: 'Tài khoản và trạng thái hoạt động', icon: 'users' },
    { id: 'role-requests', label: 'Yêu cầu nâng bậc', description: 'Xét duyệt hồ sơ thành viên', icon: 'cap' },
  ] },
  { id: 'community', label: 'Cộng đồng', icon: 'chat', items: [
    { id: 'posts', label: 'Bài viết', description: 'Quản lý nội dung được chia sẻ', icon: 'chat' },
    { id: 'reports', label: 'Báo cáo', description: 'Tiếp nhận phản ánh cộng đồng', icon: 'flag' },
    { id: 'disputes', label: 'Tranh chấp', description: 'Hỗ trợ giải quyết đơn học', icon: 'shield' },
  ] },
  { id: 'finance', label: 'Tài chính', icon: 'wallet', items: [
    { id: 'credit-packages', label: 'Gói nạp credit', description: 'Mệnh giá và số credit của gói', icon: 'wallet' },
    { id: 'cash-orders', label: 'Đơn nạp / rút', description: 'VNPAY tự động · chuyển khoản đối soát', icon: 'exchange' },
    { id: 'finance', label: 'Ví & đối soát', description: 'Sổ giao dịch và công nợ', icon: 'chart' },
    { id: 'settlements', label: 'Quyết toán gia sư', description: 'Theo dõi và giải ngân thu nhập', icon: 'check' },
  ] },
  { id: 'system', label: 'Hệ thống', icon: 'settings', items: [
    { id: 'action-logs', label: 'Nhật ký hoạt động', description: 'Lịch sử thao tác trên hệ thống', icon: 'clock' },
  ] },
]

export const adminSections = adminGroups.flatMap((group) => group.items)
export const adminHref = (section) => `/admin?section=${encodeURIComponent(section)}`
export function resolveAdminSection(location) {
  const selected = new URLSearchParams(location.split('?')[1] ?? '').get('section')
  return adminSections.find((section) => section.id === selected) ?? adminSections[0]
}
