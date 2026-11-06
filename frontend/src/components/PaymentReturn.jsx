import { Resource } from './Workspace.jsx'
import { useResource } from './workspace-utils.js'

export default function PaymentReturn({ api }) {
  const query = new URLSearchParams(window.location.search)
  const resource = useResource(api, `/payments/vnpay/return?${query.toString()}`, 0, 5000)
  return <section className="payment-return card card-body"><p className="eyebrow">Kết quả VNPAY</p><h1>Thông tin thanh toán</h1>
    <Resource resource={resource}>{(result) => <>
      <p role="status">{!result.signature_valid ? 'Không xác minh được kết quả thanh toán.'
        : result.credited ? 'Thanh toán đã được xác nhận và credit đã được cộng vào ví.'
          : result.payment_status === 'success' ? 'VNPAY báo thanh toán thành công. Hệ thống đang chờ xác nhận để cộng ví.'
            : 'Giao dịch chưa thành công. Bạn có thể kiểm tra đơn trong mục Ví.'}</p>
      <p>Trở lại tab Tutor Web ban đầu để kiểm tra ví. Nếu mở lại trang, vui lòng đăng nhập.</p>
    </>}</Resource><a className="button primary" href="/">Về Tutor Web</a>
  </section>
}
