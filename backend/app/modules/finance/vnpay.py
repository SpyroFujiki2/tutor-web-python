"""Authenticated checkout and signed, idempotent IPN crediting cash orders."""

import re
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from app.core.vnpay import VIETNAM, payment_link, payment_metadata
from app.core.vnpay_query import VNPAYQueryError, verify_query_response
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
    return apply_payment_confirmation(session, params, settings, source='ipn')


def apply_payment_confirmation(session, params, settings, *, source):
    require(source in {'ipn', 'querydr'}, 'Nguồn xác nhận thanh toán không hợp lệ')
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
              target_type='cash_order', target_id=order.id, action_code='vnpay.' + source,
              old_value={'status': order.status}, new_value={'status': target, 'provider': 'vnpay', 'transaction_no': transaction_no},
              reason='Verified VNPAY server ' + ('notification' if source == 'ipn' else 'transaction query'), created_at=now())
    if success:
        # Honor a verified payment for an existing order even if the wallet was
        # frozen during checkout. Crediting never unlocks spending or payouts.
        wallet = lock_wallets(session, order.wallet_id, require_active=False)[order.wallet_id]
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
                       'transaction_status': transaction_status, 'confirmation_source': source}
    order.status, order.updated_at = target, now()
    session.flush()
    return {'RspCode': '00', 'Message': 'Confirm Success'}


QUERY_COOLDOWN_SECONDS = 300


def verification_result(order, *, state=None, retry_after=0):
    credited = order.status == CashOrderStatus.SUCCESS
    state = 'confirmed' if credited else 'failed' if order.status == CashOrderStatus.FAILED else state or 'waiting'
    messages = {
        'confirmed': 'Thanh toán đã được xác nhận và credit đã được cộng vào ví.',
        'failed': 'Giao dịch chưa thành công. Bạn có thể kiểm tra đơn trong mục Ví.',
        'waiting': 'VNPAY chưa xác nhận thanh toán. Hệ thống sẽ tiếp tục cập nhật đơn.',
        'unavailable': 'Chưa lấy được xác nhận từ VNPAY. Vui lòng thử lại sau; bạn không cần thanh toán lại đơn này.',
    }
    return {'order_id': str(order.id), 'order_status': order.status.value, 'credited': credited,
            'verification_status': state, 'retry_after_seconds': retry_after, 'message': messages[state]}


def reserve_verification(session, user_id, order_id, settings):
    """Caller commits this short reservation BEFORE making the provider request."""
    order = get(session, CashOrder, order_id, lock=True)
    require(order.user_id == user_id, 'Không tìm thấy đơn thanh toán', LookupError)
    info = order.bank_info or {}
    require(order.order_type == CashOrderType.IN and info.get('provider') == 'vnpay',
            'Đơn này không thanh toán qua VNPAY')
    if order.status != CashOrderStatus.PENDING:
        return None, verification_result(order)
    require(info.get('tmn_code') == settings.tmn_code,
            'Đơn thuộc cấu hình VNPAY cũ; cần đối soát với đúng merchant ban đầu')
    current = int(datetime.now(UTC).timestamp())
    retry_at = info.get('query_retry_at', 0)
    if type(retry_at) is int and retry_at > current:
        return None, verification_result(order, state=info.get('query_state') if info.get('query_state') == 'unavailable' else 'waiting',
                                         retry_after=min(retry_at - current, QUERY_COOLDOWN_SECONDS))
    order.bank_info = {**info, 'query_retry_at': current + QUERY_COOLDOWN_SECONDS,
                       'query_state': 'checking', 'query_requested_at': current}
    session.flush()
    return {'metadata': dict(info), 'amount_vnd': order.amount_vnd}, None


def finish_verification(session, user_id, order_id, settings, *, result=None, error=None, transaction_no=None):
    """Fresh row lock serializes QueryDR completion against IPN crediting."""
    order = get(session, CashOrder, order_id, lock=True)
    require(order.user_id == user_id, 'Không tìm thấy đơn thanh toán', LookupError)
    if order.status != CashOrderStatus.PENDING:
        return verification_result(order)
    info = order.bank_info or {}
    require(info.get('provider') == 'vnpay' and info.get('tmn_code') == settings.tmn_code,
            'Cấu hình đơn thanh toán đã thay đổi')
    if error is None:
        try:
            params = verify_query_response(result, settings, info.get('txn_ref'), order.amount_vnd, transaction_no)
            outcome = apply_payment_confirmation(session, params, settings, source='querydr')
            if outcome['RspCode'] not in {'00', '02', '99'}:
                raise VNPAYQueryError('mismatched_response')
        except VNPAYQueryError as failure:
            error = failure
    current = int(datetime.now(UTC).timestamp())
    order.bank_info = {**order.bank_info, 'query_checked_at': current,
                       'query_state': 'unavailable' if error else 'checked',
                       'query_error_code': error.code if error else None}
    session.flush()
    return verification_result(order, state='unavailable' if error else 'waiting',
                               retry_after=QUERY_COOLDOWN_SECONDS if order.status == CashOrderStatus.PENDING else 0)
