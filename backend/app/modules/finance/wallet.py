"""Model: wallets. Mẫu: lấy ví đang hoạt động thuộc đúng chủ sở hữu."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Wallet
from app.models.enums import WalletType
from app.modules.users.user import get_active_user


def get_my_wallet(session: Session, user_id: UUID, wallet_type: WalletType) -> Wallet:
    get_active_user(session, user_id)
    wallet = session.scalar(select(Wallet).where(
        Wallet.user_id == user_id, Wallet.type == wallet_type, Wallet.is_active.is_(True),
    ))
    if wallet is None:
        raise LookupError("Active wallet not found")
    return wallet


# TODO create_wallet: cấp UUID; unique(user_id,type); ví normal không có debt,
# holding, commission hay contract; quyền mở ví commercial theo policy đã chốt.
# TODO balance_mutation: CHỈ qua service thanh toán/quyết toán; SELECT FOR UPDATE,
# kiểm tra số dư, ghi ledger và cập nhật ví cùng transaction, không setter công khai.
# TODO transfer: khóa nhiều ví theo thứ tự UUID để giảm deadlock; không nhận số dư
# trước/sau hoặc commission từ client; không dùng float cho tiền/tỷ lệ.
# TODO archived_history: quyết định quyền xem ví bị khóa; mẫu hiện chỉ đọc ví active.
