"""Immutable daily wallet snapshots and read-only ledger reconciliation."""

from datetime import datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    ActionLog,
    BookingSettlement,
    CashOrder,
    ExternalTransaction,
    InternalTransaction,
    Wallet,
    WalletSnapshot,
)
from app.models.enums import EscrowStatus, WalletType
from app.modules.common import actor, add, require
from app.modules.finance.wallet import get_my_wallet, lock_wallets


def list_my_wallet_snapshots(
    session: Session, user_id: UUID, wallet_type: WalletType, *, limit: int = 30, offset: int = 0,
) -> list[WalletSnapshot]:
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("limit must be between 1 and 100")
    wallet = get_my_wallet(session, user_id, wallet_type, include_inactive=True)
    return list(session.scalars(
        select(WalletSnapshot).where(WalletSnapshot.wallet_id == wallet.id)
        .order_by(WalletSnapshot.snapshot_date.desc().nulls_last(), WalletSnapshot.id).offset(offset).limit(limit)
    ))


# TODO daily_snapshot: chốt timezone/ngày nghiệp vụ, ý nghĩa balance_snap so với
# available_snap/holding_snap; đọc nhất quán và upsert unique(wallet_id,snapshot_date).
# TODO reconcile: đối chiếu ví với ledger và snapshot, cảnh báo lệch; snapshot
# chỉ phục vụ báo cáo, không phải nguồn cập nhật số dư khả dụng hiện tại.
# TODO backfill/archival: tác vụ có quyền, phân lô/cursor, không ghi đè lịch sử đã
# chốt nếu chưa có chính sách điều chỉnh và audit trail.


def daily_snapshots(session: Session, admin_id: UUID, *, limit: int=100, offset: int=0) -> list[WalletSnapshot]:
    actor(session, admin_id, admin=True)
    require(1 <= limit <= 100 and offset >= 0, 'Phân trang không hợp lệ')
    # Fixed UTC+7 avoids a system timezone database dependency on Windows.
    from datetime import timedelta, timezone
    day = datetime.now(timezone(timedelta(hours=7))).date()
    result = []
    for wallet in session.scalars(select(Wallet).order_by(Wallet.id).offset(offset).limit(limit).with_for_update()):
        snapshot = session.scalar(select(WalletSnapshot).where(
            WalletSnapshot.wallet_id == wallet.id, WalletSnapshot.snapshot_date == day))
        if snapshot is None:
            snapshot = add(session, WalletSnapshot, wallet_id=wallet.id, snapshot_date=day,
                           balance_snap=wallet.available_balance + wallet.holding_balance - wallet.debt,
                           available_snap=wallet.available_balance, holding_snap=wallet.holding_balance)
        result.append(snapshot)
    return result


def reconcile_wallet(session: Session, admin_id: UUID, wallet_id: UUID) -> dict:
    """Read-only reconciliation. Never rewrites balances, snapshots or old entries."""
    from app.modules.finance.external_transaction import external_checksum
    actor(session, admin_id, admin=True)
    wallet = lock_wallets(session, wallet_id, require_active=False)[wallet_id]
    issues, warnings, movements = [], [], []
    invalid_amount = False

    def issue(code, identity=None):
        item = {'code': code, 'transaction_id': str(identity) if identity else None}
        if item not in issues:
            issues.append(item)

    def movement(row, before, after, incoming):
        nonlocal invalid_amount
        if (type(row.amount) is not int or row.amount < 0 or type(before) is not int or type(after) is not int):
            issue('invalid_ledger_values', row.id)
            invalid_amount = True
            return
        delta = row.amount if incoming else -row.amount
        if after != before + delta or min(before, after) < 0:
            issue('ledger_balance_equation', row.id)
        movements.append({'id': row.id, 'created_at': row.created_at, 'before': before, 'after': after, 'delta': delta})

    internal = list(session.scalars(select(InternalTransaction).where(or_(
        InternalTransaction.source_wallet_id == wallet.id, InternalTransaction.destination_wallet_id == wallet.id))))
    for row in internal:
        incoming = row.destination_wallet_id == wallet.id
        if row.source_wallet_id == row.destination_wallet_id:
            issue('same_source_destination', row.id)
        before = row.destination_balance_before if incoming else row.source_balance_before
        after = row.destination_balance_after if incoming else row.source_balance_after
        movement(row, before, after, incoming)
        expected = sha256(f'{row.id}:{row.source_wallet_id}:{row.destination_wallet_id}:{row.amount}:'
                          f'{row.source_balance_before}:{row.destination_balance_before}'.encode()).hexdigest()
        if row.checksum != expected:
            issue('checksum_mismatch', row.id)
    external = list(session.scalars(select(ExternalTransaction).where(or_(
        ExternalTransaction.source_wallet_id == wallet.id, ExternalTransaction.destination_wallet_id == wallet.id))))
    provider_deferred = 0
    for row in external:
        incoming = row.destination_wallet_id == wallet.id
        if (row.source_wallet_id is None) == (row.destination_wallet_id is None):
            issue('invalid_external_direction', row.id)
        movement(row, row.balance_before, row.balance_after, incoming)
        order = session.get(CashOrder, row.cash_order_id) if row.cash_order_id else None
        if order and isinstance(order.bank_info, dict) and order.bank_info.get('provider') == 'vnpay':
            provider_deferred += 1
            continue
        if row.checksum != external_checksum(row.id, row.cash_order_id, row.amount, row.balance_before, row.balance_after):
            issue('checksum_mismatch', row.id)
    if provider_deferred:
        warnings.append('provider_reconciliation_deferred')
    opening = session.scalar(select(ActionLog).where(ActionLog.target_type == 'wallets', ActionLog.target_id == wallet.id,
        ActionLog.action_code == 'wallet.open').order_by(ActionLog.created_at, ActionLog.id).limit(1))
    movements.sort(key=lambda row: (row['created_at'] or datetime.min, str(row['id'])))
    baseline = 'recorded' if opening else 'derived' if movements else 'missing'
    opening_balance = (opening.new_value or {}).get('available_balance') if opening else movements[0]['before'] if movements else None
    if not opening:
        warnings.append('opening_balance_unverified')
    ambiguous = (not opening and len(movements) > 1 and movements[0]['created_at'] == movements[1]['created_at']
                 and movements[0]['before'] != movements[1]['before'])
    if ambiguous:
        warnings.append('opening_order_ambiguous')
    expected_balance = opening_balance + sum(row['delta'] for row in movements) if (
        type(opening_balance) is int and not invalid_amount and not ambiguous) else None
    if expected_balance is not None and expected_balance != wallet.available_balance:
        issue('available_balance_mismatch')
    expected_holding = sum(session.scalars(select(BookingSettlement.hold_amount).where(
        BookingSettlement.tutor_wallet_id == wallet.id, BookingSettlement.status == EscrowStatus.HELD)))
    if expected_holding != wallet.holding_balance:
        issue('holding_balance_mismatch')
    debt_log = session.scalar(select(ActionLog).where(ActionLog.target_type == 'wallets', ActionLog.target_id == wallet.id,
        ActionLog.action_code.in_(['wallet.debt', 'wallet.debt_repay']))
        .order_by(ActionLog.created_at.desc(), ActionLog.id.desc()).limit(1))
    expected_debt = (debt_log.new_value or {}).get('debt') if debt_log else (opening.new_value or {}).get('debt') if opening else None
    if expected_debt is not None and expected_debt != wallet.debt:
        issue('debt_mismatch')
    latest = session.scalar(select(WalletSnapshot).where(WalletSnapshot.wallet_id == wallet.id)
        .order_by(WalletSnapshot.snapshot_date.desc(), WalletSnapshot.id).limit(1))
    if latest and (any(value is None for value in [latest.available_snap, latest.holding_snap, latest.balance_snap])
                   or min(latest.available_snap, latest.holding_snap) < 0
                   or latest.available_snap + latest.holding_snap - latest.balance_snap < 0):
        issue('invalid_snapshot')
    return {'wallet_id': wallet.id, 'status': 'mismatch' if issues else 'ok', 'baseline_source': baseline,
            'available_balance': wallet.available_balance, 'expected_available_balance': expected_balance,
            'holding_balance': wallet.holding_balance, 'expected_holding_balance': expected_holding,
            'debt': wallet.debt, 'expected_debt': expected_debt, 'internal_count': len(internal),
            'external_count': len(external), 'issues': issues, 'warnings': warnings,
            'latest_snapshot_date': latest.snapshot_date if latest else None}
