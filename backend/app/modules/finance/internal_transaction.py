"""Credit transfers, append-only corrections, debt repayment and scoped history."""

from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import String, and_, case, cast, func, literal, or_, select, union_all
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from app.models import ActionLog, CashOrder, ExternalTransaction, InternalTransaction, Wallet
from app.models.enums import TransactionType, UserRole, WalletType
from app.modules.common import actor, add, audit, get, money, now, require
from app.modules.finance.wallet import (
    PLATFORM_WALLET_ID,
    get_my_wallet,
    lock_wallets,
    owned_wallet,
    platform_wallet,
    spendable,
)


def list_my_internal_transactions(
    session: Session, user_id: UUID, wallet_type: WalletType, *, limit: int = 50, offset: int = 0,
) -> list[RowMapping]:
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("limit must be between 1 and 100")
    wallet = get_my_wallet(session, user_id, wallet_type, include_inactive=True)
    # Không trả số dư trước/sau của ví đối tác trong ORM transaction đầy đủ.
    statement = select(
        InternalTransaction.id, InternalTransaction.type,
        InternalTransaction.amount, InternalTransaction.created_at,
    ).where(or_(
        InternalTransaction.source_wallet_id == wallet.id,
        InternalTransaction.destination_wallet_id == wallet.id,
    )).order_by(InternalTransaction.created_at.desc().nulls_last(), InternalTransaction.id).offset(offset).limit(limit)
    return list(session.execute(statement).mappings())


# TODO transfer/payment/revenue/refund: đây là kết quả của nghiệp vụ đã xác thực;
# khóa ví theo thứ tự cố định, tính balance_before/after ở server và ghi ledger
# cùng cập nhật ví/subscription/settlement trong một transaction.
# TODO amount_semantics: chốt dấu amount và đơn vị credit, int/bigint, ví nền tảng;
# hiện source/destination đều bắt buộc nên phải có ví đối ứng rõ ràng.
# TODO idempotency/checksum: thiết kế khóa duy nhất cho retry và quy tắc checksum;
# không coi checksum varchar hiện tại là cơ chế chống double-spend.
# TODO corrections: ledger bất biến; sai sót xử lý bằng giao dịch bù có audit trail.


def transfer(
    session: Session, source_id: UUID, destination_id: UUID, amount: int, kind: TransactionType, *,
    subscription_id: UUID | None = None, admin_id: UUID | None = None,
    transaction_id: UUID | None = None, ref_log_id: UUID | None = None,
    allow_inactive_destination: bool = False, allow_inactive_source: bool = False,
    allow_debt_source: bool = False,
) -> InternalTransaction:
    """Internal primitive: callers authorize the workflow and own its transaction."""
    money(amount)
    require(kind in tuple(TransactionType), 'Loại giao dịch không hợp lệ')
    require(source_id != destination_id, "Hai ví phải khác nhau")
    wallets = lock_wallets(session, source_id, destination_id, require_active=False)
    source, destination = wallets[source_id], wallets[destination_id]
    require(source.is_active or allow_inactive_source, 'Ví nguồn không hoạt động')
    require(destination.is_active or allow_inactive_destination, 'Ví đích không hoạt động')
    if transaction_id:
        existing = session.get(InternalTransaction, transaction_id, populate_existing=True)
        if existing:
            require((existing.source_wallet_id, existing.destination_wallet_id, existing.amount, existing.type,
                     existing.subscription_id) == (source_id, destination_id, amount, kind, subscription_id),
                    'Mã yêu cầu đã được dùng cho giao dịch khác')
            return existing
    require(source.debt == 0 or allow_debt_source, 'Cần thanh toán công nợ trước khi chi tiền')
    require(spendable(session, source) >= amount, "Số dư không đủ hoặc đang giữ cho đơn rút")
    source_before, dest_before = money(source.available_balance), money(destination.available_balance)
    money(dest_before + amount)
    source.available_balance -= amount
    destination.available_balance += amount
    source.updated_at = destination.updated_at = now()
    identity = transaction_id or uuid4()
    checksum = sha256(f"{identity}:{source_id}:{destination_id}:{amount}:{source_before}:{dest_before}".encode()).hexdigest()
    entry = add(session, InternalTransaction, id=identity, source_wallet_id=source_id, destination_wallet_id=destination_id,
                amount=amount, type=kind, subscription_id=subscription_id,
                source_balance_before=source_before, source_balance_after=source.available_balance,
                destination_balance_before=dest_before, destination_balance_after=destination.available_balance,
                created_by_admin_id=admin_id, ref_log_id=ref_log_id, checksum=checksum, created_at=now())
    return entry


def wallet_history(session: Session, user_id: UUID, wallet_type: WalletType, *, limit: int=20, offset: int=0) -> list[dict]:
    actor(session, user_id)
    require(1 <= limit <= 100 and offset >= 0, 'Phân trang không hợp lệ')
    wallet = owned_wallet(session, user_id, wallet_type, require_active=False)
    entries = session.scalars(select(InternalTransaction).where(or_(
        InternalTransaction.source_wallet_id == wallet.id, InternalTransaction.destination_wallet_id == wallet.id,
    )).order_by(InternalTransaction.created_at.desc().nulls_last(), InternalTransaction.id).offset(offset).limit(limit))
    return [{"id": row.id, "type": row.type, "amount": row.amount, "created_at": row.created_at,
             "direction": "out" if row.source_wallet_id == wallet.id else "in"} for row in entries]


def move_own_credits(session: Session, user_id: UUID, request_id: UUID,
                     source_type: WalletType, destination_type: WalletType, amount: int) -> InternalTransaction:
    actor(session, user_id, lock=True)
    require(source_type != destination_type and money(amount) > 0, 'Cần hai ví khác nhau và số tiền dương')
    source = owned_wallet(session, user_id, WalletType(source_type), require_active=False)
    destination = owned_wallet(session, user_id, WalletType(destination_type), require_active=False)
    existing = session.get(InternalTransaction, request_id)
    if existing:
        require(existing.source_wallet_id == source.id and existing.destination_wallet_id == destination.id
                and existing.amount == amount and existing.type == TransactionType.PAYMENT
                and existing.subscription_id is None, 'Mã yêu cầu đã được dùng cho giao dịch khác')
        return existing
    require(destination.debt == 0, 'Ví đích có công nợ; hãy dùng chức năng trả nợ')
    return transfer(session, source.id, destination.id, amount, TransactionType.PAYMENT, transaction_id=request_id)


def fund_platform(session: Session, admin_id: UUID, request_id: UUID, amount: int, reason: str) -> InternalTransaction:
    admin = actor(session, admin_id, admin=True, lock=True)
    require(admin.role == UserRole.HEAD_ADMIN, 'Cần quản trị cấp cao', PermissionError)
    require(money(amount) > 0 and 0 < len(reason.strip()) <= 200, 'Số tiền/lý do không hợp lệ')
    source = owned_wallet(session, admin.id, require_active=False)
    existing = session.get(InternalTransaction, request_id)
    if existing:
        log = session.get(ActionLog, existing.ref_log_id) if existing.ref_log_id else None
        require(existing.source_wallet_id == source.id and existing.destination_wallet_id == PLATFORM_WALLET_ID
                and existing.amount == amount and log and log.action_code == 'platform.fund', 'Mã yêu cầu đã được dùng')
        return existing
    entry = transfer(session, source.id, platform_wallet(session), amount, TransactionType.PAYMENT,
                     transaction_id=request_id, admin_id=admin.id)
    if entry.ref_log_id is None:
        log = audit(session, admin, entry, 'platform.fund', after={'amount': amount}, reason=reason)
        entry.ref_log_id = log.id
    return entry


def reverse_internal_transaction(session: Session, admin_id: UUID, transaction_id: UUID,
                                 request_id: UUID, reason: str) -> InternalTransaction:
    admin = actor(session, admin_id, admin=True)
    require(admin.role == UserRole.HEAD_ADMIN, 'Cần quản trị cấp cao lập bút toán bù', PermissionError)
    original = get(session, InternalTransaction, transaction_id, lock=True)
    require(original.subscription_id is None and original.type != TransactionType.REFUND,
            'Giao dịch dịch vụ phải hoàn qua luồng booking/khóa học; không đảo bút toán bù')
    previous = session.scalar(select(InternalTransaction).join(ActionLog, ActionLog.id == InternalTransaction.ref_log_id)
        .where(ActionLog.action_code == 'internal.reverse', ActionLog.target_id == original.id))
    if previous:
        require(previous.id == request_id, 'Giao dịch đã có bút toán bù')
        return previous
    require(session.get(InternalTransaction, request_id) is None, 'Mã yêu cầu đã được dùng')
    require(original.checksum == sha256(f'{original.id}:{original.source_wallet_id}:{original.destination_wallet_id}:'
        f'{original.amount}:{original.source_balance_before}:{original.destination_balance_before}'.encode()).hexdigest(),
        'Checksum giao dịch gốc không hợp lệ')
    log = audit(session, admin, original, 'internal.reverse', after={'amount': original.amount, 'transaction_id': str(request_id)}, reason=reason)
    return transfer(session, original.destination_wallet_id, original.source_wallet_id, original.amount,
                    TransactionType.REFUND, transaction_id=request_id, admin_id=admin.id, ref_log_id=log.id,
                    allow_inactive_destination=True)


def repay_debt(session: Session, user_id: UUID, request_id: UUID, amount: int) -> InternalTransaction:
    actor(session, user_id, lock=True)
    require(money(amount) > 0, 'Số trả nợ phải dương')
    normal = owned_wallet(session, user_id, require_active=False)
    commercial = owned_wallet(session, user_id, WalletType.COMMERCIAL, require_active=False)
    platform_id = platform_wallet(session)
    wallets = lock_wallets(session, normal.id, commercial.id, platform_id, require_active=False)
    commercial = wallets[commercial.id]
    existing = session.get(InternalTransaction, request_id)
    if existing:
        log = session.get(ActionLog, existing.ref_log_id) if existing.ref_log_id else None
        require(existing.source_wallet_id == normal.id and existing.destination_wallet_id == platform_id
                and existing.type == TransactionType.REFUND and existing.amount == amount
                and log and log.action_code == 'wallet.debt_repay' and log.target_id == commercial.id,
                'Mã yêu cầu đã được dùng cho giao dịch khác')
        return existing
    require(commercial.debt >= amount, 'Số trả vượt công nợ')
    log = add(session, ActionLog, target_user_id=user_id, target_type='wallets', target_id=commercial.id,
        action_code='wallet.debt_repay', reason='Owner repaid commercial debt',
        new_value={'amount': amount, 'debt': commercial.debt - amount, 'transaction_id': str(request_id)}, created_at=now())
    entry = transfer(session, normal.id, platform_id, amount, TransactionType.REFUND,
                     transaction_id=request_id, ref_log_id=log.id)
    commercial.debt -= amount
    commercial.updated_at = now()
    return entry


def list_admin_wallet_ledger(session: Session, admin_id: UUID, wallet_id: UUID, *, limit=20, offset=0) -> list:
    actor(session, admin_id, admin=True)
    get(session, Wallet, wallet_id)
    require(1 <= limit <= 100 and offset >= 0, 'Phân trang không hợp lệ')
    internal = select(InternalTransaction.id.label('id'), literal('internal').label('category'),
        cast(InternalTransaction.type, String).label('type'), InternalTransaction.amount.label('amount'),
        case((InternalTransaction.destination_wallet_id == wallet_id, 'in'), else_='out').label('direction'),
        case((InternalTransaction.destination_wallet_id == wallet_id, InternalTransaction.destination_balance_before),
             else_=InternalTransaction.source_balance_before).label('balance_before'),
        case((InternalTransaction.destination_wallet_id == wallet_id, InternalTransaction.destination_balance_after),
             else_=InternalTransaction.source_balance_after).label('balance_after'),
        InternalTransaction.created_at.label('created_at'),
        func.coalesce(and_(InternalTransaction.subscription_id.is_(None), InternalTransaction.type != TransactionType.REFUND), False).label('reversible')
    ).where(or_(InternalTransaction.source_wallet_id == wallet_id, InternalTransaction.destination_wallet_id == wallet_id))
    external = select(ExternalTransaction.id.label('id'), literal('external').label('category'),
        cast(literal(None), String).label('type'), ExternalTransaction.amount.label('amount'),
        case((ExternalTransaction.destination_wallet_id == wallet_id, 'in'), else_='out').label('direction'),
        ExternalTransaction.balance_before.label('balance_before'), ExternalTransaction.balance_after.label('balance_after'),
        ExternalTransaction.created_at.label('created_at'),
        and_(ExternalTransaction.cash_order_id.is_not(None),
             func.coalesce(CashOrder.bank_info['provider'].as_string(), 'manual') != 'vnpay',
             func.coalesce(ActionLog.action_code, '') != 'external.reverse').label('reversible')
    ).outerjoin(CashOrder, CashOrder.id == ExternalTransaction.cash_order_id).outerjoin(ActionLog, ActionLog.id == ExternalTransaction.ref_log_id)
    external = external.where(or_(ExternalTransaction.source_wallet_id == wallet_id, ExternalTransaction.destination_wallet_id == wallet_id))
    entries = union_all(internal, external).subquery()
    rows = list(session.execute(select(entries).order_by(entries.c.created_at.desc().nulls_last(), entries.c.id)
                               .offset(offset).limit(limit)).mappings())
    corrected = set(session.scalars(select(ActionLog.target_id).where(ActionLog.target_id.in_([row['id'] for row in rows]),
        ActionLog.action_code.in_(['internal.reverse', 'external.reverse'])))) if rows else set()
    return [{**row, 'reversible': bool(row['reversible']) and row['id'] not in corrected} for row in rows]
