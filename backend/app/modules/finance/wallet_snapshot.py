"""Model: wallet_snapshots. Mẫu: chủ ví đọc các mốc số dư gần nhất."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WalletSnapshot
from app.models.enums import WalletType
from app.modules.finance.wallet import get_my_wallet


def list_my_wallet_snapshots(
    session: Session, user_id: UUID, wallet_type: WalletType, *, limit: int = 30,
) -> list[WalletSnapshot]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    wallet = get_my_wallet(session, user_id, wallet_type)
    return list(session.scalars(
        select(WalletSnapshot).where(WalletSnapshot.wallet_id == wallet.id)
        .order_by(WalletSnapshot.snapshot_date.desc().nulls_last(), WalletSnapshot.id).limit(limit)
    ))


# TODO daily_snapshot: chốt timezone/ngày nghiệp vụ, ý nghĩa balance_snap so với
# available_snap/holding_snap; đọc nhất quán và upsert unique(wallet_id,snapshot_date).
# TODO reconcile: đối chiếu ví với ledger và snapshot, cảnh báo lệch; snapshot
# chỉ phục vụ báo cáo, không phải nguồn cập nhật số dư khả dụng hiện tại.
# TODO backfill/archival: tác vụ có quyền, phân lô/cursor, không ghi đè lịch sử đã
# chốt nếu chưa có chính sách điều chỉnh và audit trail.
