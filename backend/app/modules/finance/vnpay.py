"""Authenticated checkout and signed, idempotent IPN crediting cash orders."""

import re
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from app.core.vnpay import VIETNAM, payment_link, payment_metadata
from app.models import ActionLog, CashOrder, ExternalTransaction
from app.models.enums import CashOrderStatus, CashOrderType
from app.modules.common import add, get, money, now, require
from app.modules.finance.payments import create_deposit, lock_wallets


def checkout(session, user_id, request_id, package_id, settings, ip, bank_code=None):
    order = create_deposit(session, user_id, request_id, package_id)
    order = get(session, CashOrder, order.id, lock=True)
    require(order.status == CashOrderStatus.PENDING, 'Đơn đã được xử lý; hãy kiểm tra ví')
    metadata = order.bank_info
    if not metadata:
        metadata = payment_metadata(order.id, settings, ip, bank_code)
        order.bank_info, order.updated_at = metadata, now()
    require(metadata.get('provider') == 'vnpay' and metadata.get('tmn_code') == settings.tmn_code,
            'Đơn thuộc cấu hình thanh toán khác')
    require(datetime.fromisoformat(metadata['expires_at']) > datetime.now(VIETNAM),
            'Link thanh toán đã hết hạn; hãy tạo đơn mới')
    require(order.amount_vnd is not None and 5000 <= order.amount_vnd <= 2147483647,
            'VNPAY yêu cầu thanh toán tối thiểu 5.000đ và trong giới hạn đơn hàng')
    return {'order_id': order.id, 'payment_url': payment_link(settings, metadata, order.amount_vnd),
            'expires_at': metadata['expires_at']}


def apply_ipn(session, params, settings):
    try:
        identity = UUID(hex=params.get('vnp_TxnRef', ''))
    except (ValueError, AttributeError):
        return {'RspCode': '01', 'Message': 'Order not found'}
    order = session.get(CashOrder, identity, with_for_update=True, populate_existing=True)
    if (order is None or order.order_type != CashOrderType.IN or not order.bank_info
            or order.bank_info.get('provider') != 'vnpay'
            or order.bank_info.get('tmn_code') != settings.tmn_code
            or order.bank_info.get('txn_ref') != params.get('vnp_TxnRef')):
        return {'RspCode': '01', 'Message': 'Order not found'}
    amount = params.get('vnp_Amount', '')
    if not re.fullmatch(r'[0-9]{1,12}', amount) or int(amount) != order.amount_vnd * 100:
        return {'RspCode': '04', 'Message': 'Invalid amount'}
    if order.status != CashOrderStatus.PENDING:
        return {'RspCode': '02', 'Message': 'Order already confirmed'}
    response_code, transaction_status = params.get('vnp_ResponseCode'), params.get('vnp_TransactionStatus')
    if (not re.fullmatch(r'[0-9]{2}', response_code or '')
            or not re.fullmatch(r'[0-9]{2}', transaction_status or '')
            or params.get('vnp_CurrCode', 'VND') != 'VND'):
        return {'RspCode': '99', 'Message': 'Invalid response fields'}
    success = response_code == '00' and transaction_status == '00'
    if transaction_status in {'01', '05', '06'}:
        return {'RspCode': '99', 'Message': 'Awaiting final transaction status'}
    transaction_no = params.get('vnp_TransactionNo', '')
    if success and (not re.fullmatch(r'[0-9]{1,15}', transaction_no) or int(transaction_no) == 0):
        return {'RspCode': '99', 'Message': 'Invalid transaction reference'}
    target = CashOrderStatus.SUCCESS if success else CashOrderStatus.FAILED
    log = add(session, ActionLog, admin_id=None, target_user_id=order.user_id,
              target_type='cash_order', target_id=order.id, action_code='vnpay.ipn',
              old_value={'status': order.status}, new_value={'status': target, 'provider': 'vnpay', 'transaction_no': transaction_no},
              reason='Verified VNPAY server notification', created_at=now())
    if success:
        wallet = lock_wallets(session, order.wallet_id)[order.wallet_id]
        require(wallet.user_id == order.user_id, 'Wallet owner does not match order')
        before, credit = money(wallet.available_balance), money(order.credit_amount)
        after = money(before + credit)
        wallet.available_balance, wallet.updated_at = after, now()
        entry = add(session, ExternalTransaction, destination_wallet_id=wallet.id, amount=credit,
                    cash_order_id=order.id, balance_before=before, balance_after=after,
                    created_at=now(), ref_log_id=log.id)
        entry.checksum = sha256(f'{entry.id}:{order.id}:{transaction_no}:{credit}:{before}:{after}'.encode()).hexdigest()
    order.bank_info = {**order.bank_info, 'transaction_no': transaction_no,
                       'pay_date': params.get('vnp_PayDate'), 'response_code': response_code,
                       'transaction_status': transaction_status}
    order.status, order.updated_at = target, now()
    session.flush()
    return {'RspCode': '00', 'Message': 'Confirm Success'}
