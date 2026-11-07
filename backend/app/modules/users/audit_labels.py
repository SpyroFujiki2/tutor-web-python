"""Vietnamese display labels; persisted audit codes and snapshots stay intact."""
import unicodedata


ACTION_LABELS = {
    'admin.bootstrap': 'Khởi tạo quản trị cấp cao',
    'auth.cleanup': 'Dọn dẹp phiên đăng nhập hết hạn',
    'user.seed': 'Tạo tài khoản mẫu',
    'user.status': 'Thay đổi trạng thái người dùng',
    'course.save': 'Lưu thông tin khóa học',
    'course.grade': 'Chấm điểm khóa học',
    'course.attendance': 'Điểm danh bài học trực tiếp',
    'course.assignment': 'Xác nhận hoàn thành bài tập',
    'course.refund': 'Hoàn học phí và hủy đăng ký khóa học',
    'lesson.save': 'Lưu thông tin bài học',
    'lesson.reorder': 'Sắp xếp thứ tự bài học',
    'lesson.remove': 'Xóa bài học',
    'tutoring_package.save': 'Lưu thông tin gói gia sư',
    'tutoring_package.deactivate': 'Ngừng bán gói gia sư',
    'booking.assign': 'Phân công gia sư',
    'content.visibility': 'Thay đổi hiển thị nội dung',
    'report.claim': 'Nhận xử lý báo cáo',
    'report.resolve': 'Giải quyết báo cáo',
    'role.decide': 'Xét duyệt yêu cầu nâng bậc',
    'dispute.claim': 'Nhận xử lý tranh chấp',
    'dispute.resolve': 'Giải quyết tranh chấp',
    'cash.confirm': 'Xác nhận đơn nạp hoặc rút tiền thành công',
    'cash.fail': 'Xác nhận đơn nạp hoặc rút tiền thất bại',
    'cash.cancel': 'Hủy đơn nạp hoặc rút tiền đang chờ',
    'cash.view_bank_details': 'Xem thông tin ngân hàng nhận tiền',
    'credit_package.save': 'Lưu thông tin gói nạp credit',
    'credit_package.deactivate': 'Ngừng bán gói nạp credit',
    'wallet.open': 'Mở ví',
    'wallet.status': 'Thay đổi trạng thái ví',
    'wallet.contract': 'Cập nhật hợp đồng và phí gia sư',
    'wallet.debt': 'Ghi nhận công nợ gia sư',
    'wallet.debt_repay': 'Thanh toán công nợ gia sư',
    'platform.fund': 'Bổ sung thanh khoản cho nền tảng',
    'internal.reverse': 'Đảo giao dịch credit nội bộ',
    'external.reverse': 'Đảo giao dịch nạp hoặc rút tiền',
    'settlement.release': 'Giải ngân thu nhập gia sư',
    'settlement.refund_released': 'Hoàn credit sau khi đã giải ngân',
    'vnpay.ipn': 'Xác nhận thanh toán qua thông báo VNPAY',
    'vnpay.querydr': 'Đối soát kết quả thanh toán VNPAY',
}

TARGET_LABELS = {
    'users': 'Người dùng', 'courses': 'Khóa học', 'lessons': 'Bài học',
    'course_progress': 'Tiến độ học tập', 'user_subscriptions': 'Đăng ký học',
    'tutoring_package': 'Gói gia sư', 'booking': 'Đơn gia sư',
    'booking_sessions': 'Buổi học gia sư', 'posts': 'Bài viết', 'comments': 'Bình luận',
    'comment_report': 'Báo cáo nội dung', 'role_requests': 'Yêu cầu nâng bậc',
    'disputes': 'Tranh chấp', 'cash_order': 'Đơn nạp hoặc rút tiền',
    'credit_package': 'Gói nạp credit', 'wallets': 'Ví',
    'internal_transaction': 'Giao dịch credit nội bộ',
    'external_transaction': 'Giao dịch nạp hoặc rút tiền',
    'booking_settlements': 'Quyết toán gia sư', 'wallet_snapshots': 'Ảnh chụp số dư ví',
    'auth_sessions': 'Phiên đăng nhập', 'action_logs': 'Nhật ký hoạt động',
    'payment_method': 'Phương thức thanh toán', 'messages': 'Tin nhắn', 'attendance': 'Điểm danh',
}

# REST-style operation groups. Historical database values remain readable.
OPERATION_LABELS = {
    'GET': 'Xem (GET)', 'POST': 'Tạo mới (POST)',
    'PUT': 'Cập nhật toàn bộ (PUT)', 'PATCH': 'Cập nhật một phần (PATCH)',
    'DELETE': 'Xóa (DELETE)', 'OTHER': 'Khác',
}
LEGACY_OPERATIONS = {'SELECT': 'GET', 'INSERT': 'POST', 'UPDATE': 'PATCH'}
OPERATION_SEARCH_LABELS = {
    code: f'{label} · {description}' for code, label, description in (
        ('POST', OPERATION_LABELS['POST'], 'Thêm dữ liệu Tạo mới'),
        ('GET', OPERATION_LABELS['GET'], 'Xem dữ liệu Đọc dữ liệu'),
        ('PUT', OPERATION_LABELS['PUT'], 'Sửa dữ liệu Cập nhật toàn bộ'),
        ('PATCH', OPERATION_LABELS['PATCH'], 'Sửa dữ liệu Cập nhật một phần'),
        ('DELETE', OPERATION_LABELS['DELETE'], 'Xóa dữ liệu'),
        ('OTHER', OPERATION_LABELS['OTHER'], 'Thao tác khác'),
    )
}
ACTION_OPERATIONS = {
    **dict.fromkeys(('admin.bootstrap', 'user.seed', 'wallet.open', 'platform.fund',
                     'internal.reverse', 'external.reverse'), 'POST'),
    **dict.fromkeys(('auth.cleanup', 'lesson.remove'), 'DELETE'),
    'cash.view_bank_details': 'GET',
    **dict.fromkeys(('user.status', 'course.grade', 'course.attendance', 'course.assignment', 'lesson.reorder',
                     'tutoring_package.deactivate', 'credit_package.deactivate', 'booking.assign',
                     'content.visibility', 'report.claim', 'report.resolve', 'role.decide',
                     'dispute.claim', 'dispute.resolve', 'cash.confirm', 'cash.fail', 'cash.cancel',
                     'wallet.status', 'wallet.contract', 'wallet.debt', 'wallet.debt_repay',
                     'settlement.release', 'vnpay.ipn', 'vnpay.querydr', 'course.refund',
                     'settlement.refund_released'), 'PATCH'),
    # Older save events did not distinguish create from update.
    **dict.fromkeys(('course.save', 'lesson.save', 'tutoring_package.save', 'credit_package.save'), 'OTHER'),
}


def operation_for(code, stored=None):
    if stored in OPERATION_LABELS:
        return stored
    if stored == 'UPDATE':
        return 'PUT' if code and code.endswith('.save') else 'PATCH'
    if stored in LEGACY_OPERATIONS:
        return LEGACY_OPERATIONS[stored]
    return ACTION_OPERATIONS.get(code, 'OTHER')

REASON_LABELS = {
    'Explicit local bootstrap': 'Khởi tạo tài khoản quản trị theo yêu cầu',
    'Explicit local demo seed: one account per role': 'Tạo tài khoản mẫu cho từng vai trò',
    'Explicit local demo seed': 'Khởi tạo dữ liệu mẫu',
    'Wallet opened with zero balances': 'Mở ví với số dư ban đầu bằng 0',
    'Owner cancelled pending manual order': 'Chủ tài khoản hủy đơn thủ công đang chờ xử lý',
    'Owner repaid commercial debt': 'Chủ tài khoản thanh toán công nợ ví gia sư',
    'Tutor income set off against debt': 'Khấu trừ thu nhập gia sư để thanh toán công nợ',
    'Remove sessions expired more than 30 days ago': 'Xóa các phiên đăng nhập đã hết hạn hơn 30 ngày',
    'Verified VNPAY server notification': 'Đã xác minh thông báo thanh toán từ VNPAY',
    'Verified VNPAY server transaction query': 'Đã xác minh kết quả đối soát giao dịch từ VNPAY',
}


def action_label(code):
    return ACTION_LABELS.get(code, 'Thao tác khác' if code else 'Thao tác hệ thống')


def target_label(code):
    return TARGET_LABELS.get(code, code or '—')


def reason_label(reason):
    return REASON_LABELS.get(reason, reason)


def matching_codes(labels, query):
    def normalize(value):
        value = unicodedata.normalize('NFD', value.casefold().replace('đ', 'd'))
        return ''.join(character for character in value if not unicodedata.combining(character))
    needle = normalize(query.strip())
    return [code for code, label in labels.items() if needle and needle in normalize(label)]
