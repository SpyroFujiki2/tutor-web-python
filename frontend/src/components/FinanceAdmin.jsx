import { useState } from 'react'
import { Action, Details, Form, Pager, Resource } from './Workspace.jsx'
import { money, numberField, reasonField, textField, useResource } from './workspace-utils.js'

const issueLabels = {
  available_balance_mismatch: 'Số dư khả dụng không khớp ledger', holding_balance_mismatch: 'Tiền tạm giữ không khớp quyết toán',
  debt_mismatch: 'Công nợ không khớp lịch sử', checksum_mismatch: 'Dấu kiểm tra giao dịch không khớp',
  ledger_balance_equation: 'Số dư trước/sau giao dịch không đúng', invalid_ledger_values: 'Giao dịch thiếu hoặc sai dữ liệu',
  same_source_destination: 'Giao dịch có cùng ví nguồn và đích', invalid_external_direction: 'Chiều giao dịch ngoài không hợp lệ',
  invalid_snapshot: 'Snapshot không hợp lệ',
}

export default function FinanceAdmin({ api, user }) {
  const [offset, setOffset] = useState(0)
  const [version, setVersion] = useState(0)
  const wallets = useResource(api, `/admin/wallets?limit=20&offset=${offset}`, version)
  const treasury = useResource(api, '/admin/finance/treasury', version)
  const [jobResult, setJobResult] = useState('')
  const [jobSkips, setJobSkips] = useState([])
  const refresh = () => setVersion((value) => value + 1)
  return <section><div className="row"><h2>Ví và đối soát nội bộ</h2><button onClick={refresh}>Làm mới</button></div>
    <Resource resource={treasury}>{(row) => <div className="card card-body"><h3>Ví nền tảng</h3><Details row={row} fields={['available_balance', 'spendable_balance']} /><p className="muted">Khoản còn tạm giữ cho gia sư được trừ khỏi phần có thể chi.</p>
      {user.role === 'head_admin' && <details><summary>Bổ sung thanh khoản từ ví cá nhân của bạn</summary><Form fields={[numberField('amount', 'Số credit', { min: 1 }), reasonField]} submit="Chuyển credit vào nền tảng" onSubmit={async (values, requestId) => {
        await api.request('/admin/finance/treasury/fund', { method: 'POST', body: { ...values, request_id: requestId } }); refresh()
      }} /></details>}</div>}</Resource>
    <div className="actions"><Action onClick={async () => {
      const result = await api.request('/admin/jobs/release-settlements?limit=20', { method: 'POST' })
      setJobResult(`Đã giải ngân ${result.released.length} quyết toán; bỏ qua ${result.skipped.length}.`); setJobSkips(result.skipped); refresh()
    }}>Giải ngân tối đa 20 quyết toán đến hạn</Action></div>
    <details><summary>Chụp số dư theo lô</summary><Form fields={[numberField('limit', 'Số ví trong lô', { min: 1, max: 100, default: 100 }), numberField('offset', 'Bỏ qua số ví', { default: 0 })]} submit="Chụp số dư hôm nay" onSubmit={async ({ limit, offset: start }) => {
      const rows = await api.request(`/admin/jobs/snapshots?limit=${limit}&offset=${start}`, { method: 'POST' })
      setJobResult(`Đã ghi nhận ${rows.length} snapshot. Snapshot cùng ngày được giữ nguyên.`)
      setJobSkips([])
    }} /></details>{jobResult && <p role="status" className="success">{jobResult}</p>}
    {jobSkips.length > 0 && <ul>{jobSkips.map((row) => <li key={row.settlement_id}>Quyết toán {row.settlement_id}: {row.detail}</li>)}</ul>}
    <Resource resource={wallets}>{(rows) => <><div className="stack">{rows.map((row) => <WalletAdmin key={row.id} api={api} user={user} wallet={row} refresh={refresh} />)}</div><Pager offset={offset} setOffset={setOffset} length={rows.length} /></>}</Resource>
  </section>
}

function WalletAdmin({ api, user, wallet, refresh }) {
  const [open, setOpen] = useState(false)
  const [report, setReport] = useState(null)
  const [offset, setOffset] = useState(0)
  const ledger = useResource(api, open ? `/admin/wallets/${wallet.id}/ledger?limit=20&offset=${offset}` : null)
  return <article className="card card-body"><h3>{wallet.type === 'normal' ? 'Ví cá nhân' : 'Ví gia sư'} · {wallet.is_active ? 'Đang hoạt động' : 'Đang khóa'}</h3><Details row={wallet} fields={['id', 'user_id', 'available_balance', 'spendable_balance', 'reserved_withdrawals', 'holding_balance', 'debt', 'commission_rate', 'contract_id']} />
    <Action onClick={async () => setReport(await api.request(`/admin/wallets/${wallet.id}/reconciliation`))}>Đối soát ví</Action>
    {report && <div className={`notice ${report.status === 'ok' ? 'success' : 'error'}`}><strong>{report.status === 'ok' ? 'Các số liệu kiểm tra khớp.' : 'Phát hiện số liệu lệch.'}</strong><p>Số dư theo ledger: {report.expected_available_balance === null ? 'Chưa đủ dữ liệu' : money(report.expected_available_balance)} credit.</p>
      <ul>{report.issues.map((item, index) => <li key={index}>{issueLabels[item.code] ?? item.code}{item.transaction_id ? ` · ${item.transaction_id}` : ''}</li>)}</ul>
      {report.warnings.includes('opening_balance_unverified') && <p>Ví cũ chưa có mốc mở ví được xác minh; kết quả dùng dữ liệu lịch sử hiện có.</p>}{report.warnings.includes('provider_reconciliation_deferred') && <p>Các giao dịch nhà cung cấp cần được đối soát ở giai đoạn riêng.</p>}</div>}
    {user.role === 'head_admin' && <><details><summary>Khóa / mở ví</summary><Form fields={[{ name: 'is_active', label: 'Trạng thái', options: [{ value: 'true', label: 'Hoạt động' }, { value: 'false', label: 'Khóa' }] }, reasonField]} onSubmit={async (values) => {
      await api.request(`/admin/wallets/${wallet.id}/status`, { method: 'POST', body: { ...values, is_active: values.is_active === 'true' } }); refresh()
    }} /></details>{wallet.type === 'commercial' && <details><summary>Cấu hình hợp đồng gia sư</summary><Form fields={[numberField('commission_rate', 'Phí nền tảng (%)', { max: 100 }), textField('contract_id', 'Mã hợp đồng', { optional: true, maxLength: 200 }), reasonField]} initial={wallet} onSubmit={async (values) => {
      await api.request(`/admin/wallets/${wallet.id}/contract`, { method: 'POST', body: values }); refresh()
    }} /></details>}</>}
    <details onToggle={(event) => setOpen(event.currentTarget.open)}><summary>Sổ giao dịch của ví</summary><Resource resource={ledger}>{(rows) => <><div className="stack">{rows.map((row) => <div className="inset" key={`${row.category}-${row.id}`}><p>{row.category === 'internal' ? 'Nội bộ' : 'Nạp / rút'}</p><Details row={row} fields={['id', 'type', 'amount', 'direction', 'balance_before', 'balance_after', 'created_at']} />
      {user.role === 'head_admin' && row.reversible && <details><summary>Lập bút toán bù sau đối soát</summary><p>Giao dịch gốc được giữ nguyên. Với nạp/rút, chỉ thực hiện sau khi đã xác minh điều chỉnh tiền ngoài hệ thống.</p><Form fields={[reasonField]} submit="Xác nhận bút toán bù" onSubmit={async (values, requestId) => {
        await api.request(`/admin/${row.category}-transactions/${row.id}/reverse`, { method: 'POST', body: { ...values, request_id: requestId } }); ledger.reload(); refresh()
      }} /></details>}
    </div>)}</div><Pager offset={offset} setOffset={setOffset} length={rows.length} /></>}</Resource></details>
  </article>
}
