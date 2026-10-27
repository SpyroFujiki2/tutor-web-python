"""Model: external_transaction. Mẫu: đọc lịch sử nạp/rút liên quan ví của user."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from app.models import ExternalTransaction
from app.models.enums import WalletType
from app.modules.finance.wallet import get_my_wallet


def list_my_external_transactions(
    session: Session, user_id: UUID, wallet_type: WalletType, *, limit: int = 50,
) -> list[RowMapping]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    wallet = get_my_wallet(session, user_id, wallet_type)
    statement = select(
        ExternalTransaction.id, ExternalTransaction.amount,
        ExternalTransaction.cash_order_id, ExternalTransaction.created_at,
    ).where(or_(
        ExternalTransaction.source_wallet_id == wallet.id,
        ExternalTransaction.destination_wallet_id == wallet.id,
    )).order_by(ExternalTransaction.created_at.desc().nulls_last(), ExternalTransaction.id).limit(limit)
    return list(session.execute(statement).mappings())


# TODO deposit_callback: xác thực nhà cung cấp, đối chiếu cash_order, số tiền/đơn vị;
# khóa order/ví, chống callback lặp và chỉ cộng số dư khi xác minh thành công.
# TODO withdrawal: xác thực chủ ví, bank_info snapshot, duyệt/rút theo chính sách;
# tách gọi nhà cung cấp khỏi DB transaction dài, theo dõi retry/reconciliation.
# TODO provider_reference: schema chưa có khóa idempotency/reference nhà cung cấp;
# thiết kế cột/bảng bổ sung và unique trước khi xử lý tiền thật.
# TODO ledger: không chỉnh/xóa giao dịch đã ghi; hoàn/điều chỉnh bằng bản ghi bù.
