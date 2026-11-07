import { useState } from 'react'
import { Action, Badge, Details, Form, Pager, Resource } from './Workspace.jsx'
import { money, numberField, textField, useResource } from './workspace-utils.js'
import PageHeading from './PageHeading.jsx'
import Icon from './Icon.jsx'

const bankFields = [textField('bank_name', 'Ngân hàng'), textField('account_number', 'Số tài khoản', { minLength: 4, maxLength: 40 }), textField('account_holder_name', 'Tên chủ tài khoản')]

export default function Wallet({ api, user }) {
  const [version, setVersion] = useState(0)
  const wallets = useResource(api, '/me/wallets', version, 15000)
  const packages = useResource(api, '/credit-packages?limit=100')
  const banks = useResource(api, '/me/payment-methods', version)
  const [offset, setOffset] = useState(0)
  const orders = useResource(api, `/me/cash-orders?limit=20&offset=${offset}`, version, 15000)
  const [reviewPackage, setReviewPackage] = useState(null)
  const [paymentLink, setPaymentLink] = useState(null)
  const [verification, setVerification] = useState(null)
  const vnpay = useResource(api, '/payments/vnpay/status')
  const [historyType, setHistoryType] = useState('normal')
  const refresh = () => setVersion((value) => value + 1)
  return <section className="wallet-page"><PageHeading eyebrow="CHỦ ĐỘNG CHO HÀNH TRÌNH HỌC" title="Ví & thanh toán" description="Quản lý credit, nạp học phí và theo dõi mọi giao dịch của bạn." icon="wallet" />
    <Resource resource={wallets}>{(rows) => <div className="card-grid">{rows.map((row) => <article className="card wallet-card" key={row.id}>
      <Badge value={row.type} /><p className="balance">{money(row.available_balance)} <small>credit</small></p><Details row={row} fields={['spendable_balance', 'reserved_withdrawals', 'holding_balance', 'debt', 'commission_rate']} />
      {!row.is_active && <p>Ví đang khóa. Bạn vẫn có thể xem lịch sử.</p>}
      <button onClick={() => setHistoryType(row.type)}>Xem lịch sử</button>
    </article>)}</div>}</Resource>
    {['tutor', 'admin', 'head_admin'].includes(user.role) && !wallets.data?.some((row) => row.type === 'commercial') && <Action onClick={async () => { await api.request('/me/wallets', { method: 'POST', body: { type: 'commercial' } }); refresh() }}>Mở ví gia sư</Action>}
    {wallets.data?.filter((row) => row.is_active && row.debt === 0).length === 2 && <details><summary>Chuyển credit giữa hai ví của bạn</summary><Form fields={[
      { name: 'source_type', label: 'Ví nguồn', options: ['normal', 'commercial'], default: 'commercial' },
      { name: 'destination_type', label: 'Ví đích', options: ['normal', 'commercial'], default: 'normal' },
      numberField('amount', 'Số credit', { min: 1 }),
    ]} submit="Xác nhận chuyển" onSubmit={async (values, requestId) => {
      await api.request('/me/transfers', { method: 'POST', body: { ...values, request_id: requestId } }); refresh()
    }} /></details>}
    {wallets.data?.some((row) => row.type === 'commercial' && row.debt > 0) && <div className="card card-body"><h2>Thanh toán công nợ gia sư</h2><p>Credit được chuyển từ ví cá nhân về nền tảng để giảm công nợ. Thu nhập gia sư sau này cũng được bù công nợ trước khi có thể rút.</p>
      <Form fields={[numberField('amount', 'Số credit trả nợ', { min: 1 })]} submit="Xác nhận trả nợ" onSubmit={async (values, requestId) => {
        await api.request('/me/debt-repayments', { method: 'POST', body: { ...values, request_id: requestId } }); refresh()
      }} /></div>}
    <div className="notice payment-policy"><Icon name="shield" size={22} /><div><strong>Nạp VNPAY, nhận credit tự động</strong><p>Thanh toán VNPAY thành công sẽ tự cộng ví sau khi hệ thống nhận xác nhận. Bạn không cần chờ admin duyệt. Chuyển khoản thủ công và rút tiền được quản trị đối soát.</p></div></div>
    <h2>Nạp credit</h2><Resource resource={packages} empty="Chưa có gói nạp.">{(rows) => <div className="card-grid">{rows.map((row) => <article className="card card-body" key={row.id}>
      <h3>{row.name}</h3><p><strong>{money(row.credits)} credit</strong> · {money(row.price)} đ</p><button onClick={() => setReviewPackage(row)}>Chọn gói</button>
    </article>)}</div>}</Resource>
    {reviewPackage && <div className="card card-body"><h3>Xác nhận yêu cầu nạp</h3><p>{money(reviewPackage.price)} đ → {money(reviewPackage.credits)} credit. VNPAY tự xác nhận thanh toán; chuyển khoản cần quản trị đối soát.</p>
      {vnpay.data?.enabled && vnpay.data.sandbox && <p className="notice">VNPAY đang ở môi trường thử nghiệm. Sử dụng thẻ test, không thanh toán bằng tiền thật.</p>}
      <Form fields={[{ name: 'provider', label: 'Cách thanh toán', options: [
        ...(vnpay.data?.enabled ? [{ value: 'vnpay', label: vnpay.data.sandbox ? 'VNPAY sandbox (thử nghiệm)' : 'VNPAY' }] : []),
        { value: 'manual', label: 'Chuyển khoản, quản trị xác nhận' },
      ], default: vnpay.data?.enabled ? 'vnpay' : 'manual' }]} submit="Tạo đơn nạp" onSubmit={async ({ provider }, requestId) => {
        const body = { request_id: requestId, package_id: reviewPackage.id }
        if (provider === 'vnpay') setPaymentLink(await api.request('/payments/vnpay/checkout', { method: 'POST', body }))
        else await api.request('/me/deposits', { method: 'POST', body })
        setReviewPackage(null); refresh()
      }} />
      <button onClick={() => setReviewPackage(null)}>Đóng</button></div>}
    {paymentLink && <div className="notice success"><p>Đơn nạp đã tạo. Tiếp tục đến VNPAY để thanh toán trước khi liên kết hết hạn.</p><a className="button primary" href={paymentLink.payment_url}>Thanh toán qua VNPAY →</a><button onClick={() => setPaymentLink(null)}>Đóng</button></div>}
    <div className="split"><section className="card card-body"><h2>Tài khoản nhận tiền</h2><Resource resource={banks} empty="Chưa thêm tài khoản ngân hàng.">{(rows) => <ul className="plain-list">{rows.map((bank) => <li key={bank.id}>
      <strong>{bank.bank_name} · {bank.account_number_masked}</strong><p>{bank.account_holder_name}</p><Action onClick={async () => { await api.request(`/me/payment-methods/${bank.id}`, { method: 'DELETE' }); refresh() }}>Xóa tài khoản</Action>
      <details><summary>Sửa thông tin ngân hàng</summary><Form fields={bankFields} initial={{ bank_name: bank.bank_name, account_holder_name: bank.account_holder_name }} onSubmit={async (values) => {
        await api.request(`/me/payment-methods/${bank.id}`, { method: 'PUT', body: values }); refresh()
      }} /></details>
    </li>)}</ul>}</Resource><details><summary>Thêm ngân hàng</summary><Form fields={bankFields} reset onSubmit={async (values) => { await api.request('/me/payment-methods', { method: 'POST', body: values }); refresh() }} /></details></section>
      <section className="card card-body"><h2>Yêu cầu rút tiền</h2><p>Quy đổi rút: 1 credit = 1 VND.</p>
        {banks.data?.length > 0 && wallets.data && <Form key={version} fields={[
          { name: 'wallet_type', label: 'Ví nguồn', options: wallets.data.filter((row) => row.is_active).map((row) => row.type), default: 'normal' },
          { name: 'payment_method_id', label: 'Ngân hàng nhận', options: banks.data.map((row) => ({ value: row.id, label: `${row.bank_name} ${row.account_number_masked}` })) },
          numberField('amount', 'Số credit rút', { min: 1 }),
        ]} submit="Tạo đơn rút" onSubmit={async (values, requestId) => { await api.request('/me/withdrawals', { method: 'POST', body: { ...values, request_id: requestId } }); refresh() }} />}
      </section></div>
    <h2>Đơn nạp / rút</h2><button onClick={refresh}>Cập nhật số dư & đơn</button><Resource resource={orders} empty="Chưa có đơn thanh toán.">{(rows) => <><div className="card-grid">{rows.map((row) => <article className="card card-body" key={row.id}><Badge value={row.status} /><p>{row.provider === 'vnpay' ? 'VNPAY' : 'Xác nhận thủ công'}</p><Details row={row} fields={['id', 'order_type', 'credit_amount', 'amount_vnd', 'created_at']} />
      {row.provider === 'vnpay' && <p className={`payment-state ${row.status === 'success' ? 'is-success' : ''}`}><Icon name={row.status === 'success' ? 'check' : 'clock'} size={17} />{row.status === 'success' ? 'Đã cộng credit vào ví.' : row.status === 'pending' ? 'Chờ VNPAY xác nhận · Không cần admin duyệt.' : 'Đã cập nhật theo kết quả thanh toán VNPAY.'}</p>}
      {row.provider === 'vnpay' && row.status === 'pending' && <Action onClick={async () => {
        const result = await api.request(`/payments/vnpay/orders/${row.id}/verify`, { method: 'POST', body: {} })
        setVerification({ ...result, id: row.id }); refresh()
      }}><Icon name="refresh" size={16} />Kiểm tra thanh toán</Action>}
      {verification?.id === row.id && <p role="status">{verification.message}</p>}
      {row.provider === 'vnpay' && row.status === 'pending' && <Action onClick={async () => setPaymentLink(await api.request('/payments/vnpay/checkout', { method: 'POST', body: { request_id: row.id, package_id: row.package_id } }))}>Mở lại thanh toán VNPAY</Action>}
      {row.provider !== 'vnpay' && row.status === 'pending' && <Action onClick={async () => {
        await api.request(`/me/cash-orders/${row.id}/cancel`, { method: 'POST' }); refresh()
      }}>Hủy đơn đang chờ</Action>}
      {row.cancelled_by_user && <p className="muted">Bạn đã hủy yêu cầu này.</p>}
    </article>)}</div><Pager offset={offset} setOffset={setOffset} length={rows.length} /></>}</Resource>
    <WalletHistory key={`${historyType}-${version}`} api={api} type={historyType} />
  </section>
}

function WalletHistory({ api, type }) {
  const [kind, setKind] = useState('history')
  const [offset, setOffset] = useState(0)
  const resource = useResource(api, `/me/wallets/${type}/${kind}?limit=20&offset=${offset}`)
  return <section><h2>Lịch sử {type === 'normal' ? 'ví cá nhân' : 'ví gia sư'}</h2><div className="tabs">
    {[['history', 'Thanh toán dịch vụ'], ['external-history', 'Nạp / rút'], ['snapshots', 'Số dư theo ngày']].map(([value, label]) => <button key={value} aria-pressed={kind === value} onClick={() => { setKind(value); setOffset(0) }}>{label}</button>)}
  </div><Resource resource={resource} empty="Chưa có giao dịch.">{(rows) => <><div className="stack">{rows.map((row) => <article className="card card-body" key={row.id}>
    <Details row={row} fields={['type', 'direction', 'amount', 'created_at', 'balance_before', 'balance_after', 'snapshot_date', 'balance_snap', 'available_snap', 'holding_snap']} />
  </article>)}</div><Pager offset={offset} setOffset={setOffset} length={rows.length} /></>}</Resource></section>
}
