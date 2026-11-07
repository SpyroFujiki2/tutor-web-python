"""VNPAY QueryDR 2.1.0: bounded HTTPS requests and verified responses.

QueryDR uses a pipe-separated HMAC payload, unlike PAY/IPN query strings.
Protocol: https://sandbox.vnpayment.vn/apis/docs/truy-van-hoan-tien/querydr%26refund.html
"""

import hmac
import json
import re
from datetime import datetime
from hashlib import sha512
from http.client import HTTPException
from ipaddress import ip_address
from socket import gaierror
from ssl import SSLError
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from app.core.config import runtime_values
from app.core.vnpay import VIETNAM

REQUEST_FIELDS = (
    'vnp_RequestId', 'vnp_Version', 'vnp_Command', 'vnp_TmnCode', 'vnp_TxnRef',
    'vnp_TransactionDate', 'vnp_CreateDate', 'vnp_IpAddr', 'vnp_OrderInfo',
)
RESPONSE_FIELDS = (
    'vnp_ResponseId', 'vnp_Command', 'vnp_ResponseCode', 'vnp_Message',
    'vnp_TmnCode', 'vnp_TxnRef', 'vnp_Amount', 'vnp_BankCode', 'vnp_PayDate',
    'vnp_TransactionNo', 'vnp_TransactionType', 'vnp_TransactionStatus',
    'vnp_OrderInfo', 'vnp_PromotionCode', 'vnp_PromotionAmount',
)


class VNPAYQueryError(Exception):
    def __init__(self, code, request_id=None):
        # Never propagate provider bodies, request URLs, signatures or secrets.
        super().__init__('VNPAY payment verification is temporarily unavailable')
        self.code = code
        self.request_id = request_id


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def query_signature(values, fields, secret):
    parts = []
    for key in fields:
        value = values.get(key)
        if value is None:
            value = ''
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            raise VNPAYQueryError('invalid_response')
        parts.append(str(value))
    return hmac.new(secret.encode(), '|'.join(parts).encode(), sha512).hexdigest()


def query_url(settings):
    if settings.payment_url == 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html':
        return 'https://sandbox.vnpayment.vn/merchant_webapi/api/transaction'
    return 'https://merchantapi.vnpay.vn/merchant_webapi/api/transaction'


def query_server_ip(server_host=None):
    """Use server configuration/ASGI listener, never client or forwarded headers.

    A listener behind NAT is not its public egress IP. Deployments needing that
    value must configure VNPAY_QUERY_IP from their known network configuration.
    """
    configured = runtime_values().get('VNPAY_QUERY_IP')
    candidate = configured if configured else server_host
    try:
        address = ip_address(candidate)
        if address.is_unspecified or address.is_multicast or '%' in str(address):
            raise ValueError('Not a server address')
    except (TypeError, ValueError):
        if configured:
            raise VNPAYQueryError('invalid_server_ip') from None
        return '127.0.0.1'
    # The protocol's IP field has a minimum length of seven characters.
    return str(address) if len(str(address)) >= 7 else address.exploded


def transport_error_code(error):
    if isinstance(error, TimeoutError):
        return 'timeout'
    if isinstance(error, SSLError):
        return 'tls_error'
    if isinstance(error, gaierror):
        return 'dns_error'
    return 'network_error'


def build_query(settings, metadata, ip, transaction_no=None):
    try:
        ip_address(ip)
    except (TypeError, ValueError):
        raise VNPAYQueryError('invalid_server_ip') from None
    if not re.fullmatch(r'[0-9]{14}', metadata.get('create_date', '')):
        raise VNPAYQueryError('invalid_order')
    if not re.fullmatch(r'[0-9a-f]{32}', metadata.get('txn_ref', '')):
        raise VNPAYQueryError('invalid_order')
    payload = {
        'vnp_RequestId': uuid4().hex, 'vnp_Version': '2.1.0', 'vnp_Command': 'querydr',
        'vnp_TmnCode': settings.tmn_code, 'vnp_TxnRef': metadata['txn_ref'],
        'vnp_TransactionDate': metadata['create_date'],
        'vnp_CreateDate': datetime.now(VIETNAM).strftime('%Y%m%d%H%M%S'),
        'vnp_IpAddr': ip, 'vnp_OrderInfo': 'Query payment ' + metadata['txn_ref'],
    }
    if transaction_no is not None:
        if not re.fullmatch(r'[0-9]{1,15}', transaction_no) or int(transaction_no) == 0:
            raise VNPAYQueryError('invalid_transaction')
        payload['vnp_TransactionNo'] = transaction_no
    payload['vnp_SecureHash'] = query_signature(payload, REQUEST_FIELDS, settings.hash_secret)
    return payload


def verify_query_response(values, settings, txn_ref, amount_vnd, transaction_no=None):
    if not isinstance(values, dict):
        raise VNPAYQueryError('invalid_response')
    code = values.get('vnp_ResponseCode')
    if code != '00':
        raise VNPAYQueryError(code if isinstance(code, str) and re.fullmatch(r'[0-9]{2}', code) else 'invalid_response')
    digest = values.get('vnp_SecureHash', '')
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-fA-F]{128}', digest):
        raise VNPAYQueryError('invalid_signature')
    expected = query_signature(values, RESPONSE_FIELDS, settings.hash_secret)
    if not hmac.compare_digest(expected, digest.lower()):
        raise VNPAYQueryError('invalid_signature')
    amount = str(values.get('vnp_Amount', ''))
    # Optional in QueryDR responses. Verify the original empty field in the HMAC
    # above; never insert a default command before checking the signature.
    if (values.get('vnp_Command') not in {None, '', 'querydr'} or values.get('vnp_TmnCode') != settings.tmn_code
            or values.get('vnp_TxnRef') != txn_ref or values.get('vnp_TransactionType') != '01'
            or not re.fullmatch(r'[0-9]{1,12}', amount) or int(amount) != amount_vnd * 100):
        raise VNPAYQueryError('mismatched_response')
    if transaction_no is not None and str(values.get('vnp_TransactionNo')) != transaction_no:
        raise VNPAYQueryError('mismatched_response')
    status = values.get('vnp_TransactionStatus')
    if not isinstance(status, str) or not re.fullmatch(r'[0-9]{2}', status):
        raise VNPAYQueryError('invalid_response')
    reference = str(values.get('vnp_TransactionNo', ''))
    if status == '00' and (not re.fullmatch(r'[0-9]{1,15}', reference) or int(reference) == 0):
        raise VNPAYQueryError('invalid_transaction')
    return {key: str(value) for key, value in values.items() if value is not None}


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise VNPAYQueryError('invalid_response')
        result[key] = value
    return result


def query_transaction(settings, metadata, amount_vnd, ip, transaction_no=None):
    payload = build_query(settings, metadata, ip, transaction_no)
    request = Request(query_url(settings), data=json.dumps(payload).encode(), method='POST',
                      headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with build_opener(NoRedirects()).open(request, timeout=8) as response:
            raw = response.read(65537)
            if response.status != 200:
                code = f'http_{response.status}' if type(response.status) is int and 100 <= response.status <= 599 else 'invalid_response'
                raise VNPAYQueryError(code)
            if len(raw) > 65536:
                raise VNPAYQueryError('response_too_large')
            values = json.loads(raw, object_pairs_hook=unique_json_object)
        return verify_query_response(values, settings, metadata['txn_ref'], amount_vnd, transaction_no)
    except VNPAYQueryError as error:
        error.request_id = payload['vnp_RequestId']
        raise
    except HTTPError as error:
        code = f'http_{error.code}' if type(error.code) is int and 100 <= error.code <= 599 else 'http_error'
        raise VNPAYQueryError(code, payload['vnp_RequestId']) from None
    except URLError as error:
        raise VNPAYQueryError(transport_error_code(error.reason), payload['vnp_RequestId']) from None
    except HTTPException:
        raise VNPAYQueryError('http_protocol_error', payload['vnp_RequestId']) from None
    except OSError as error:
        raise VNPAYQueryError(transport_error_code(error), payload['vnp_RequestId']) from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise VNPAYQueryError('invalid_json', payload['vnp_RequestId']) from None
    except ValueError:
        raise VNPAYQueryError('invalid_response', payload['vnp_RequestId']) from None
