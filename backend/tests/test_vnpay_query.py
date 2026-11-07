import hmac
import json
import secrets
import unittest
from hashlib import sha512
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from uuid import UUID, uuid4

from sqlalchemy import event, func, select

from app.core.vnpay import VNPAYSettings
from app.core.vnpay_query import (
    RESPONSE_FIELDS, VNPAYQueryError, build_query, query_signature,
    query_transaction, verify_query_response,
)
from app.models import ActionLog, CashOrder, ExternalTransaction
from test_vnpay import VNPAYFixture


class QueryProtocolTests(unittest.TestCase):
    def setUp(self):
        self.settings = VNPAYSettings(tmn_code='TEST1234', hash_secret=secrets.token_hex(32),
                                      return_url='https://tutor.example/payment/vnpay-return')
        self.metadata = {'txn_ref': uuid4().hex, 'create_date': '20261107122133'}

    def response(self, **changes):
        value = {'vnp_ResponseId': uuid4().hex, 'vnp_Command': 'querydr', 'vnp_ResponseCode': '00',
                 'vnp_Message': 'Success', 'vnp_TmnCode': self.settings.tmn_code,
                 'vnp_TxnRef': self.metadata['txn_ref'], 'vnp_Amount': '2000000',
                 'vnp_BankCode': 'NCB', 'vnp_PayDate': '20261107122154',
                 'vnp_TransactionNo': '15728677', 'vnp_TransactionType': '01',
                 'vnp_TransactionStatus': '00', 'vnp_OrderInfo': 'Nap credit',
                 'vnp_PromotionCode': '', 'vnp_PromotionAmount': 0, **changes}
        value['vnp_SecureHash'] = query_signature(value, RESPONSE_FIELDS, self.settings.hash_secret)
        return value

    def test_query_request_uses_pipe_signing_and_original_create_date_without_zero_transaction(self):
        payload = build_query(self.settings, self.metadata, '127.0.0.1')
        self.assertNotIn('vnp_TransactionNo', payload)
        self.assertEqual(payload['vnp_TransactionDate'], self.metadata['create_date'])
        expected = '|'.join([payload['vnp_RequestId'], '2.1.0', 'querydr', 'TEST1234',
                             self.metadata['txn_ref'], self.metadata['create_date'],
                             payload['vnp_CreateDate'], '127.0.0.1', payload['vnp_OrderInfo']])
        self.assertEqual(payload['vnp_SecureHash'], hmac.new(
            self.settings.hash_secret.encode(), expected.encode(), sha512).hexdigest())
        self.assertNotIn(self.settings.hash_secret, json.dumps(payload))
        with self.assertRaises(VNPAYQueryError):
            build_query(self.settings, self.metadata, '127.0.0.1', '0')

    def test_response_requires_matching_signature_quote_reference_merchant_type_and_transaction(self):
        response = self.response()
        verified = verify_query_response(response, self.settings, self.metadata['txn_ref'], 20000, '15728677')
        self.assertEqual(verified['vnp_PromotionAmount'], '0')
        for changes in ({'vnp_Amount': '1'}, {'vnp_TmnCode': 'OTHER123'}, {'vnp_TxnRef': uuid4().hex},
                        {'vnp_TransactionType': '02'}, {'vnp_TransactionNo': '0'}, {'vnp_TransactionStatus': 'bad'}):
            with self.subTest(changes=changes), self.assertRaises(VNPAYQueryError):
                verify_query_response(self.response(**changes), self.settings, self.metadata['txn_ref'], 20000)
        with self.assertRaises(VNPAYQueryError):
            verify_query_response({**response, 'vnp_Message': 'Tampered'}, self.settings, self.metadata['txn_ref'], 20000)
        with self.assertRaises(VNPAYQueryError):
            verify_query_response(response, self.settings, self.metadata['txn_ref'], 20000, '99999')

    def test_transport_posts_only_to_provider_and_sanitizes_failures(self):
        response = MagicMock(status=200)
        response.read.return_value = json.dumps(self.response()).encode()
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = response
        with patch('app.core.vnpay_query.build_opener', return_value=opener):
            result = query_transaction(self.settings, self.metadata, 20000, '127.0.0.1', '15728677')
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.full_url, 'https://sandbox.vnpayment.vn/merchant_webapi/api/transaction')
        self.assertEqual(json.loads(request.data)['vnp_TransactionNo'], '15728677')
        self.assertEqual(result['vnp_TransactionStatus'], '00')
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 8)
        opener.open.side_effect = URLError(self.settings.hash_secret)
        with patch('app.core.vnpay_query.build_opener', return_value=opener), self.assertRaises(VNPAYQueryError) as caught:
            query_transaction(self.settings, self.metadata, 20000, '127.0.0.1')
        self.assertNotIn(self.settings.hash_secret, str(caught.exception))
        self.assertEqual(caught.exception.code, 'unavailable')

    def test_unsigned_99_duplicate_keys_and_oversized_responses_are_never_confirmations(self):
        for raw in (b'{"vnp_ResponseCode":"99","vnp_Message":"Unexpected error"}',
                    b'{"vnp_ResponseCode":"00","vnp_ResponseCode":"99"}', b'x' * 65537):
            response = MagicMock(status=200)
            response.read.return_value = raw
            opener = MagicMock()
            opener.open.return_value.__enter__.return_value = response
            with self.subTest(size=len(raw)), patch('app.core.vnpay_query.build_opener', return_value=opener):
                with self.assertRaises(VNPAYQueryError):
                    query_transaction(self.settings, self.metadata, 20000, '127.0.0.1')


class PaymentVerificationTests(VNPAYFixture):
    def query_response(self, order, **changes):
        value = {'vnp_ResponseId': uuid4().hex, 'vnp_Command': 'querydr', 'vnp_ResponseCode': '00',
                 'vnp_Message': 'Success', 'vnp_TmnCode': self.settings.tmn_code,
                 'vnp_TxnRef': UUID(order['order_id']).hex, 'vnp_Amount': '5000000',
                 'vnp_BankCode': 'NCB', 'vnp_PayDate': '20261107122154',
                 'vnp_TransactionNo': '15728677', 'vnp_TransactionType': '01',
                 'vnp_TransactionStatus': '00', 'vnp_OrderInfo': 'Nap credit', **changes}
        value['vnp_SecureHash'] = query_signature(value, RESPONSE_FIELDS, self.settings.hash_secret)
        return value

    def verify(self, order, *, who='customer', expected=200, body=None):
        return self.request('POST', '/payments/vnpay/orders/' + order['order_id'] + '/verify',
                            {} if body is None else body, who=who, expected=expected)

    def test_verified_query_credits_automatically_once_and_late_ipn_cannot_duplicate(self):
        order = self.checkout()
        with patch('app.api.routes.vnpay.query_transaction', return_value=self.query_response(order)) as query:
            first = self.verify(order)
            second = self.verify(order)
        self.assertTrue(first['credited'])
        self.assertTrue(second['credited'])
        self.assertEqual(query.call_count, 1)
        self.assertEqual(self.balance(), 1200)
        self.assertEqual(self.ipn(self.callback(order))['RspCode'], '02')
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalTransaction)), 1)
            log = session.scalar(select(ActionLog).where(ActionLog.action_code == 'vnpay.querydr'))
            self.assertIsNotNone(log)

    def test_provider_failure_keeps_order_pending_and_throttles_retries_across_requests(self):
        order = self.checkout()
        with patch('app.api.routes.vnpay.query_transaction', side_effect=VNPAYQueryError('99')) as query:
            first = self.verify(order)
            second = self.verify(order)
        self.assertFalse(first['credited'])
        self.assertEqual(first['verification_status'], 'unavailable')
        self.assertEqual(second['verification_status'], 'unavailable')
        self.assertGreater(second['retry_after_seconds'], 0)
        self.assertEqual(query.call_count, 1)
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(self.request('GET', '/me/cash-orders')[0]['status'], 'pending')
        self.assertEqual(self.ipn(self.callback(order))['RspCode'], '00')
        self.assertTrue(self.verify(order)['credited'])

    def test_query_is_owner_only_and_requires_login_before_contacting_provider(self):
        order = self.checkout()
        with patch('app.api.routes.vnpay.query_transaction') as query:
            self.verify(order, who='other', expected=404)
            self.verify(order, who=None, expected=401)
        query.assert_not_called()
        self.assertEqual(self.balance(), 1000)

    def test_invalid_response_or_refund_cannot_credit_even_if_transport_is_mocked(self):
        for changes in ({'vnp_TmnCode': 'OTHER123'}, {'vnp_Amount': '1'},
                        {'vnp_TransactionType': '02'}, {'vnp_SecureHash': '0' * 128}):
            order = self.checkout()
            response = self.query_response(order, **changes)
            if 'vnp_SecureHash' in changes:
                response['vnp_SecureHash'] = changes['vnp_SecureHash']
            with patch('app.api.routes.vnpay.query_transaction', return_value=response):
                result = self.verify(order)
            self.assertFalse(result['credited'])
            self.assertEqual(result['verification_status'], 'unavailable')
        self.assertEqual(self.balance(), 1000)

    def test_ipn_arriving_during_query_wins_and_query_cannot_overwrite_the_confirmation(self):
        order = self.checkout()
        def query_and_notify(*args):
            self.assertEqual(self.ipn(self.callback(order))['RspCode'], '00')
            return self.query_response(order)
        with patch('app.api.routes.vnpay.query_transaction', side_effect=query_and_notify):
            result = self.verify(order)
        self.assertTrue(result['credited'])
        self.assertEqual(self.balance(), 1200)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalTransaction)), 1)
            self.assertEqual(session.get(CashOrder, UUID(order['order_id'])).bank_info['confirmation_source'], 'ipn')

    def test_unfinished_query_never_credits_and_old_merchant_order_does_not_use_new_keys(self):
        order = self.checkout()
        with patch('app.api.routes.vnpay.query_transaction', return_value=self.query_response(order, vnp_TransactionStatus='01')):
            result = self.verify(order)
        self.assertFalse(result['credited'])
        self.assertEqual(self.balance(), 1000)
        with self.factory.begin() as session:
            row = session.get(CashOrder, UUID(order['order_id']))
            row.bank_info = {**row.bank_info, 'tmn_code': 'OLD12345'}
        with patch('app.api.routes.vnpay.query_transaction') as query:
            self.verify(order, expected=400)
        query.assert_not_called()

    def test_signed_return_exposes_support_reference_but_still_does_not_credit(self):
        from urllib.parse import urlencode
        order = self.checkout()
        result = self.client.get('/api/payments/vnpay/return?' + urlencode(self.callback(order))).json()
        self.assertEqual(result['order_id'], order['order_id'])
        self.assertEqual(result['transaction_no'], '123456789')
        self.assertEqual(result['credit_amount'], 200)
        self.assertFalse(result['credited'])
        self.assertEqual(self.balance(), 1000)

    def test_failed_posting_commit_rolls_back_money_and_ipn_can_recover(self):
        from sqlalchemy.exc import OperationalError
        order = self.checkout()
        commits = 0
        def fail_second_commit(_session):
            nonlocal commits
            commits += 1
            if commits == 2:
                raise OperationalError('test', None, Exception('commit failed'))
        event.listen(self.factory, 'before_commit', fail_second_commit)
        try:
            with patch('app.api.routes.vnpay.query_transaction', return_value=self.query_response(order)):
                self.verify(order, expected=503)
        finally:
            event.remove(self.factory, 'before_commit', fail_second_commit)
        self.assertEqual(self.balance(), 1000)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalTransaction)), 0)
        self.assertEqual(self.ipn(self.callback(order))['RspCode'], '00')
        self.assertEqual(self.balance(), 1200)
