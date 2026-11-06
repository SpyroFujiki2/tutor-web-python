"""Wallet ownership, withdrawal/escrow reservations and administrative policy."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActionLog, BookingSettlement, CashOrder, User, Wallet
from app.models.enums import CashOrderStatus, CashOrderType, EscrowStatus, UserRole, UserStatus, WalletType
from app.modules.common import actor, add, audit, get, money, now, require


PLATFORM_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
PLATFORM_WALLET_ID = UUID("00000000-0000-0000-0000-000000000002")


def get_my_wallet(session: Session, user_id: UUID, wallet_type: WalletType, *, include_inactive: bool = False) -> Wallet:
    actor(session, user_id)
    return owned_wallet(session, user_id, wallet_type, require_active=not include_inactive)


# TODO create_wallet: cấp UUID; unique(user_id,type); ví normal không có debt,
# holding, commission hay contract; quyền mở ví commercial theo policy đã chốt.
# TODO balance_mutation: CHỈ qua service thanh toán/quyết toán; SELECT FOR UPDATE,
# kiểm tra số dư, ghi ledger và cập nhật ví cùng transaction, không setter công khai.
# TODO transfer: khóa nhiều ví theo thứ tự UUID để giảm deadlock; không nhận số dư
# trước/sau hoặc commission từ client; không dùng float cho tiền/tỷ lệ.
# TODO archived_history: quyết định quyền xem ví bị khóa; mẫu hiện chỉ đọc ví active.


def platform_wallet(session: Session) -> UUID:
    if session.bind.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    session.execute(insert(User).values(id=PLATFORM_USER_ID, role=UserRole.GUEST,
        status=UserStatus.SUSPENDED, created_at=now()).on_conflict_do_nothing(index_elements=['id']))
    user = session.get(User, PLATFORM_USER_ID, populate_existing=True)
    require(user.role == UserRole.GUEST and user.status == UserStatus.SUSPENDED
            and user.email is None and user.password_hash is None, 'Tài khoản hệ thống không hợp lệ')
    created = session.execute(insert(Wallet).values(id=PLATFORM_WALLET_ID, user_id=PLATFORM_USER_ID,
        type=WalletType.NORMAL, available_balance=0, holding_balance=0, debt=0,
        is_active=True, created_at=now(), updated_at=now()).on_conflict_do_nothing(index_elements=['id'])
        .returning(Wallet.id)).scalar_one_or_none()
    wallet = session.get(Wallet, PLATFORM_WALLET_ID, populate_existing=True)
    require(wallet.user_id == PLATFORM_USER_ID and wallet.type == WalletType.NORMAL and wallet.is_active,
            'Ví hệ thống không hợp lệ')
    if created:
        record_opening_balance(session, wallet)
    return PLATFORM_WALLET_ID


def owned_wallet(session: Session, user_id: UUID, wallet_type: WalletType=WalletType.NORMAL, *, require_active: bool=True) -> Wallet:
    wallet_type = WalletType(wallet_type)
    wallet = session.scalar(select(Wallet).where(Wallet.user_id == user_id, Wallet.type == wallet_type))
    require(wallet is not None and (wallet.is_active or not require_active), "Không tìm thấy ví hoạt động", LookupError)
    return wallet


def lock_wallets(session: Session, *ids: UUID, require_active: bool=True) -> dict[UUID, Wallet]:
    rows = list(session.scalars(select(Wallet).where(Wallet.id.in_(ids))
                               .order_by(Wallet.id).with_for_update().execution_options(populate_existing=True)))
    require(len(rows) == len(set(ids)) and (not require_active or all(row.is_active for row in rows)), "Ví không hoạt động")
    return {row.id: row for row in rows}


def spendable(session: Session, wallet: Wallet) -> int:
    require(type(wallet.available_balance) is int and wallet.available_balance >= 0, 'Số dư ví không hợp lệ')
    pending = reserved_withdrawals(session, wallet)
    escrow = 0
    if wallet.id == PLATFORM_WALLET_ID:
        holds = list(session.scalars(select(BookingSettlement.hold_amount).where(BookingSettlement.status == EscrowStatus.HELD)))
        escrow = sum(money(value) for value in holds)
    return wallet.available_balance - pending - escrow


def create_wallet(session: Session, user_id: UUID, wallet_type: WalletType) -> Wallet:
    wallet_type = WalletType(wallet_type)
    user = actor(session, user_id, lock=True)
    if wallet_type == WalletType.COMMERCIAL:
        require(user.role in {UserRole.TUTOR, UserRole.ADMIN, UserRole.HEAD_ADMIN},
                "Chỉ gia sư được mở ví kinh doanh", PermissionError)
    existing = session.scalar(select(Wallet).where(Wallet.user_id == user_id, Wallet.type == wallet_type))
    if existing:
        return existing
    wallet = add(session, Wallet, id=uuid4(), user_id=user_id, type=wallet_type,
               available_balance=0, holding_balance=0, debt=0, is_active=True,
               commission_rate=10 if wallet_type == WalletType.COMMERCIAL else None,
               created_at=now(), updated_at=now())
    record_opening_balance(session, wallet)
    return wallet


def record_opening_balance(session: Session, wallet: Wallet) -> None:
    add(session, ActionLog, target_user_id=wallet.user_id, target_type='wallets', target_id=wallet.id,
        action_code='wallet.open', reason='Wallet opened with zero balances', created_at=now(),
        new_value={'available_balance': 0, 'holding_balance': 0, 'debt': 0})


def set_wallet_status(session: Session, admin_id: UUID, wallet_id: UUID, is_active: bool, reason: str) -> Wallet:
    admin = actor(session, admin_id, admin=True)
    require(admin.role == UserRole.HEAD_ADMIN, 'Cần quản trị cấp cao quản lý ví', PermissionError)
    require(wallet_id != PLATFORM_WALLET_ID, 'Không khóa ví hệ thống')
    require(type(is_active) is bool and 0 < len(reason.strip()) <= 200, 'Trạng thái/lý do không hợp lệ')
    wallet = get(session, Wallet, wallet_id, lock=True)
    before = {'is_active': wallet.is_active}
    wallet.is_active, wallet.updated_at = is_active, now()
    audit(session, admin, wallet, 'wallet.status', before=before, after={'is_active': is_active}, reason=reason)
    return wallet


def configure_commercial_wallet(
    session: Session, admin_id: UUID, wallet_id: UUID, commission_rate: int, contract_id: str | None, reason: str,
) -> Wallet:
    admin = actor(session, admin_id, admin=True)
    require(admin.role == UserRole.HEAD_ADMIN, 'Cần quản trị cấp cao cấu hình hợp đồng', PermissionError)
    require(type(commission_rate) is int and 0 <= commission_rate <= 100, 'Phí phải trong 0–100%')
    require(contract_id is None or len(contract_id.strip()) <= 200, 'Mã hợp đồng quá dài')
    wallet = get(session, Wallet, wallet_id, lock=True)
    require(wallet.type == WalletType.COMMERCIAL, 'Chỉ cấu hình ví gia sư')
    before = {'commission_rate': wallet.commission_rate, 'contract_id': wallet.contract_id}
    wallet.commission_rate, wallet.contract_id = commission_rate, contract_id.strip() if contract_id else None
    wallet.updated_at = now()
    audit(session, admin, wallet, 'wallet.contract', before=before,
          after={'commission_rate': commission_rate, 'contract_id': wallet.contract_id}, reason=reason)
    return wallet


def wallet_summary(session: Session, wallet: Wallet) -> dict:
    fields = ('id', 'user_id', 'type', 'available_balance', 'holding_balance', 'debt',
              'commission_rate', 'contract_id', 'is_active', 'created_at', 'updated_at')
    pending = reserved_withdrawals(session, wallet)
    return {**{name: getattr(wallet, name) for name in fields}, 'reserved_withdrawals': pending,
            'spendable_balance': max(0, spendable(session, wallet)) if wallet.is_active and wallet.debt == 0 else 0}


def reserved_withdrawals(session: Session, wallet: Wallet) -> int:
    pending = list(session.scalars(select(CashOrder).where(CashOrder.wallet_id == wallet.id,
        CashOrder.order_type == CashOrderType.OUT, CashOrder.status == CashOrderStatus.PENDING)))
    for order in pending:
        require(order.user_id == wallet.user_id and money(order.credit_amount) > 0, 'Đơn rút có dữ liệu không hợp lệ, cần đối soát')
    return sum(order.credit_amount for order in pending)
