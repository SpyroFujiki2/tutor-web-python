import { useCallback, useEffect, useRef, useState } from 'react'
import { Action, Resource } from './Workspace.jsx'
import { money, useResource } from './workspace-utils.js'
import SiteLink from './SiteLink.jsx'
import Icon from './Icon.jsx'

export default function PaymentReturn({ api, user }) {
  const query = new URLSearchParams(window.location.search)
  const resource = useResource(api, `/payments/vnpay/return?${query.toString()}`, 0, 5000)
  return <section className="payment-return card card-body"><span className="payment-result-icon"><Icon name="wallet" size={32} /></span><p className="eyebrow">KẾT QUẢ VNPAY</p><h1>Thông tin thanh toán</h1>
    <Resource resource={resource}>{(result) => <PaymentResult key={result.order_id ?? 'invalid'} api={api} user={user} result={result} />}</Resource><SiteLink className="button primary" href="/wallet">Về ví của tôi<Icon name="arrow" size={17} /></SiteLink><SiteLink href="/" className="text-button">Về trang chủ</SiteLink>
  </section>
}

function PaymentResult({ api, user, result }) {
  const [verification, setVerification] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [cooldown, setCooldown] = useState(0)
  const attempted = useRef(false)
  const inFlight = useRef(false)
  const credited = result.credited || verification?.credited
  const { order_id: orderId, transaction_no: transactionNo } = result
  const pending = result.signature_valid && result.payment_status === 'success' &&
    result.order_status === 'pending' && orderId && !credited && verification?.order_status !== 'failed'
  const check = useCallback(async () => {
    if (inFlight.current) return
    attempted.current = true
    inFlight.current = true
    setBusy(true); setError('')
    try {
      const next = await api.request(`/payments/vnpay/orders/${orderId}/verify`, {
        method: 'POST', body: transactionNo ? { transaction_no: transactionNo } : {},
      })
      setVerification(next)
      setCooldown(next.retry_after_seconds ?? 0)
    } catch (failure) { setError(failure.message) }
    finally { inFlight.current = false; setBusy(false) }
  }, [api, orderId, transactionNo])
  useEffect(() => {
    if (!user || !pending) return
    const timer = setTimeout(() => { if (!attempted.current) check() }, 15000)
    return () => clearTimeout(timer)
  }, [check, pending, user])
  useEffect(() => {
    if (!cooldown) return
    const timer = setTimeout(() => setCooldown(0), cooldown * 1000)
    return () => clearTimeout(timer)
  }, [cooldown])
  const message = !result.signature_valid ? 'Không xác minh được kết quả thanh toán.'
    : credited ? 'Thanh toán đã được xác nhận và credit đã được cộng vào ví.'
      : verification?.message ?? (result.payment_status === 'success' && result.order_status === 'pending'
        ? 'VNPAY báo thanh toán thành công. Hệ thống đang xác nhận để cộng ví.'
        : 'Giao dịch chưa thành công. Bạn có thể kiểm tra đơn trong mục Ví.')
  return <>
    <p role="status">{busy ? 'Đang đối chiếu kết quả thanh toán với VNPAY…' : message}</p>
    {orderId && <div className="inset"><p>{money(result.amount_vnd)}đ → <strong>{money(result.credit_amount)} credit</strong></p>
      {transactionNo && <p>Mã giao dịch VNPAY: <strong>{transactionNo}</strong></p>}<small>Mã đơn: {orderId}</small></div>}
    {pending && user && <><Action disabled={busy || cooldown > 0} onClick={check}><Icon name="refresh" size={16} />Kiểm tra lại thanh toán</Action>
      {cooldown > 0 && <p className="muted">Có thể kiểm tra lại sau tối đa 5 phút. Bạn không cần thanh toán lại đơn này.</p>}</>}
    {error && <p className="notice error" role="alert">{error}</p>}
    {!credited && <p>Đơn được cộng credit khi có xác nhận hợp lệ từ VNPAY, không cần admin duyệt.</p>}
  </>
}
