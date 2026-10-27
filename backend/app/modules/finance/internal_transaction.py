"""Model: internal_transaction. Mẫu: lịch sử rút gọn của một ví do user sở hữu."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from app.models import InternalTransaction
from app.models.enums import WalletType
from app.modules.finance.wallet import get_my_wallet


def list_my_internal_transactions(
    session: Session, user_id: UUID, wallet_type: WalletType, *, limit: int = 50,
) -> list[RowMapping]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    wallet = get_my_wallet(session, user_id, wallet_type)
    # Không trả số dư trước/sau của ví đối tác trong ORM transaction đầy đủ.
    statement = select(
        InternalTransaction.id, InternalTransaction.type,
        InternalTransaction.amount, InternalTransaction.created_at,
    ).where(or_(
        InternalTransaction.source_wallet_id == wallet.id,
        InternalTransaction.destination_wallet_id == wallet.id,
    )).order_by(InternalTransaction.created_at.desc().nulls_last(), InternalTransaction.id).limit(limit)
    return list(session.execute(statement).mappings())


# TODO transfer/payment/revenue/refund: đây là kết quả của nghiệp vụ đã xác thực;
# khóa ví theo thứ tự cố định, tính balance_before/after ở server và ghi ledger
# cùng cập nhật ví/subscription/settlement trong một transaction.
# TODO amount_semantics: chốt dấu amount và đơn vị credit, int/bigint, ví nền tảng;
# hiện source/destination đều bắt buộc nên phải có ví đối ứng rõ ràng.
# TODO idempotency/checksum: thiết kế khóa duy nhất cho retry và quy tắc checksum;
# không coi checksum varchar hiện tại là cơ chế chống double-spend.
# TODO corrections: ledger bất biến; sai sót xử lý bằng giao dịch bù có audit trail.
