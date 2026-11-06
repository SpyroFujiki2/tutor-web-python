"""VNPAY PAY 2.1.0 URL signing; no secrets or payment decisions in the browser.

Protocol: https://sandbox.vnpayment.vn/apis/docs/thanh-toan-pay/pay.html
"""

import hmac
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha512
from ipaddress import ip_address
from urllib.parse import urlencode, urlsplit

from dotenv import dotenv_values

from app.core.config import ROOT_DIR

VIETNAM = timezone(timedelta(hours=7))


@dataclass(frozen=True)
class VNPAYSettings:
    tmn_code: str
    hash_secret: str = field(repr=False)
    return_url: str
    payment_url: str = 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html'
    expires_minutes: int = 15

    def __post_init__(self):
        if not re.fullmatch(r'[A-Za-z0-9]{8}', self.tmn_code) or not self.hash_secret:
            raise ValueError('Configure VNPAY_TMN_CODE and VNPAY_HASH_SECRET')
        if self.payment_url not in {
            'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html',
            'https://pay.vnpay.vn/vpcpay.html',
        }:
            raise ValueError('VNPAY_PAYMENT_URL must be an official VNPAY endpoint')
        url = urlsplit(self.return_url)
        if (url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password
                or url.fragment or url.query or len(self.return_url) > 255):
            raise ValueError('VNPAY_RETURN_URL must be an HTTP(S) URL without query or credentials')
        if url.scheme == 'http' and url.hostname not in {'localhost', '127.0.0.1', '::1'}:
            raise ValueError('VNPAY_RETURN_URL requires HTTPS outside localhost')
        if not 5 <= self.expires_minutes <= 60:
            raise ValueError('VNPAY expiry must be 5..60 minutes')


def get_vnpay_settings() -> VNPAYSettings | None:
    values = {**dotenv_values(ROOT_DIR / '.env'), **os.environ}
    if not values.get('VNPAY_TMN_CODE') and not values.get('VNPAY_HASH_SECRET'):
        return None
    return VNPAYSettings(
        tmn_code=values.get('VNPAY_TMN_CODE') or '', hash_secret=values.get('VNPAY_HASH_SECRET') or '',
        return_url=values.get('VNPAY_RETURN_URL') or 'http://localhost:5173/payment/vnpay-return',
        payment_url=values.get('VNPAY_PAYMENT_URL') or 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html',
        expires_minutes=int(values.get('VNPAY_EXPIRES_MINUTES') or '15'),
    )


def canonical_query(params: dict[str, str]) -> str:
    return urlencode(sorted((key, value) for key, value in params.items()
                            if key.startswith('vnp_') and key not in {'vnp_SecureHash', 'vnp_SecureHashType'} and value != ''))


def signature(params: dict[str, str], secret: str) -> str:
    return hmac.new(secret.encode(), canonical_query(params).encode(), sha512).hexdigest()


def verified_query(items, settings: VNPAYSettings) -> dict[str, str] | None:
    params = {}
    for key, value in items:
        if not key.startswith('vnp_'):
            continue
        if key in params or len(value) > 4096:
            return None
        params[key] = value
    digest = params.get('vnp_SecureHash', '')
    if not re.fullmatch(r'[0-9a-fA-F]{128}', digest):
        return None
    if params.get('vnp_SecureHashType', 'HMACSHA512').upper() != 'HMACSHA512':
        return None
    if not hmac.compare_digest(signature(params, settings.hash_secret), digest.lower()):
        return None
    if params.get('vnp_TmnCode') != settings.tmn_code:
        return None
    return params


def payment_link(settings: VNPAYSettings, metadata: dict, amount_vnd: int) -> str:
    ip_address(metadata['ip_address'])
    params = {
        'vnp_Version': '2.1.0', 'vnp_Command': 'pay', 'vnp_TmnCode': settings.tmn_code,
        'vnp_Amount': str(amount_vnd * 100), 'vnp_CurrCode': 'VND',
        'vnp_TxnRef': metadata['txn_ref'], 'vnp_OrderInfo': 'Nap credit ' + metadata['txn_ref'],
        'vnp_OrderType': 'other', 'vnp_Locale': 'vn', 'vnp_ReturnUrl': settings.return_url,
        'vnp_IpAddr': metadata['ip_address'], 'vnp_CreateDate': metadata['create_date'],
        'vnp_ExpireDate': metadata['expire_date'],
    }
    if metadata.get('bank_code'):
        params['vnp_BankCode'] = metadata['bank_code']
    return settings.payment_url + '?' + canonical_query(params) + '&vnp_SecureHash=' + signature(params, settings.hash_secret)


def payment_metadata(order_id, settings: VNPAYSettings, ip: str, bank_code: str | None):
    created = datetime.now(VIETNAM).replace(microsecond=0)
    expires = created + timedelta(minutes=settings.expires_minutes)
    return {'provider': 'vnpay', 'tmn_code': settings.tmn_code, 'txn_ref': order_id.hex,
            'ip_address': str(ip_address(ip)), 'bank_code': bank_code,
            'create_date': created.strftime('%Y%m%d%H%M%S'),
            'expire_date': expires.strftime('%Y%m%d%H%M%S'), 'expires_at': expires.isoformat()}
