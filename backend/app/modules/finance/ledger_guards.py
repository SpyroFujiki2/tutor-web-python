"""Application ORM guard for monetary history; SQL operators remain auditable."""

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, object_session

from app.models import ExternalTransaction, InternalTransaction, WalletSnapshot


def immutable_update(_mapper, _connection, target):
    state = inspect(target)
    session = object_session(target)
    for column in target.__table__.columns:
        history = state.attrs[column.key].history
        if not history.has_changes():
            continue
        if not isinstance(target, WalletSnapshot) and column.key in {'checksum', 'ref_log_id'}:
            # Only a row inserted in this still-open transaction may finish metadata.
            pending = state.info.get('ledger_pending_metadata', set())
            token = session.info.get('ledger_transaction_token') if session else None
            if token is not None and state.info.get('ledger_transaction_token') is token and column.key in pending:
                pending.remove(column.key)
                continue
        raise ValueError('Không sửa lịch sử tiền/snapshot đã ghi; dùng bút toán bù')


def immutable_delete(_mapper, _connection, _target):
    raise ValueError('Không xóa lịch sử tiền/snapshot đã ghi; dùng bút toán bù')


def track_new_ledger(_mapper, _connection, target):
    session = object_session(target)
    state = inspect(target)
    state.info['ledger_transaction_token'] = session.info.setdefault('ledger_transaction_token', object())
    state.info['ledger_pending_metadata'] = {name for name in ('checksum', 'ref_log_id') if getattr(target, name) is None}


def clear_transaction_token(session, transaction):
    if transaction.parent is None:
        session.info.pop('ledger_transaction_token', None)


def install_ledger_guards():
    for model in (InternalTransaction, ExternalTransaction, WalletSnapshot):
        if not event.contains(model, 'before_update', immutable_update):
            event.listen(model, 'before_update', immutable_update)
            event.listen(model, 'before_delete', immutable_delete)
    for model in (InternalTransaction, ExternalTransaction):
        if not event.contains(model, 'before_insert', track_new_ledger):
            event.listen(model, 'before_insert', track_new_ledger)
    if not event.contains(Session, 'after_transaction_end', clear_transaction_token):
        event.listen(Session, 'after_transaction_end', clear_transaction_token)
