import { Resource } from './Workspace.jsx'
import { useResource } from './workspace-utils.js'
import SiteLink from './SiteLink.jsx'
import Icon from './Icon.jsx'

export default function PaymentReturn({ api }) {
  const query = new URLSearchParams(window.location.search)
  const resource = useResource(api, `/payments/vnpay/return?${query.toString()}`, 0, 5000)
  return <section className="payment-return card card-body"><span className="payment-result-icon"><Icon name="wallet" size={32} /></span><p className="eyebrow">KẾT QUẢ VNPAY</p><h1>Thông tin thanh toán</h1>
    <Resource resource={resource}>{(result) => <>
      <p role="status">{!result.signature_valid ? 'Không xác minh được kết quả thanh toán.'
        : result.credited ? 'Thanh toán đã được xác nhận và credit đã được cộng vào ví.'
          : result.payment_status === 'success' ? 'VNPAY báo thanh toán thành công. Hệ thống đang chờ xác nhận để cộng ví.'
            : 'Giao dịch chưa thành công. Bạn có thể kiểm tra đơn trong mục Ví.'}</p>
      <p>Thanh toán thành công được cộng credit tự động, không cần admin duyệt. Bạn có thể trở về ví để kiểm tra số dư.</p>
    </>}</Resource><SiteLink className="button primary" href="/wallet">Về ví của tôi<Icon name="arrow" size={17} /></SiteLink><SiteLink href="/" className="text-button">Về trang chủ</SiteLink>
  </section>
}
