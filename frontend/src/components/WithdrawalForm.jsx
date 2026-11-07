import { Form } from './Workspace.jsx'
import { money, numberField } from './workspace-utils.js'

export default function WithdrawalForm({ wallets, banks, onSubmit }) {
  const wallet = wallets.find((row) => row.type === 'commercial')
  if (!wallet) return <p className="muted">Ví cá nhân không hỗ trợ rút tiền. Chức năng này chỉ dành cho ví gia sư.</p>
  if (!wallet.is_active) return <p className="muted">Ví gia sư đang khóa nên chưa thể rút tiền.</p>
  if (wallet.debt > 0) return <p className="muted">Bạn cần thanh toán hết công nợ ví gia sư trước khi rút tiền.</p>
  if (Number(wallet.spendable_balance ?? 0) <= 0) return <p className="muted">Ví gia sư chưa có số dư khả dụng để rút.</p>
  if (!banks.length) return <p className="muted">Thêm tài khoản ngân hàng nhận tiền để rút từ ví gia sư.</p>
  return <><p>Ví nguồn: <strong>Ví gia sư</strong> · Có thể rút: <strong>{money(wallet.spendable_balance)} credit</strong></p><Form fields={[
    { name: 'payment_method_id', label: 'Ngân hàng nhận', options: banks.map((row) => ({ value: row.id, label: `${row.bank_name} ${row.account_number_masked}` })) },
    numberField('amount', 'Số credit rút', { min: 1, max: Math.max(0, Number(wallet.spendable_balance ?? 0)) }),
  ]} submit="Tạo đơn rút" onSubmit={(values, requestId) => onSubmit({ ...values, wallet_type: 'commercial' }, requestId)} /></>
}
