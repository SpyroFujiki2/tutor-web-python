import secrets
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.api.routes.vnpay import configured_settings
from app.core.vnpay import VNPAYSettings, signature, verified_query
from app.models import ExternalTransaction
from test_domain_api import DomainApiFixture


class VNPAYFixture(DomainApiFixture):
    def setUp(self):
        super().setUp()
        self.client.close()
        self.client = TestClient(self.app, client=('127.0.0.1', 50000))
        self.addCleanup(self.client.close)
        self.settings = VNPAYSettings(tmn_code='TEST1234', hash_secret=secrets.token_hex(32),
                                     return_url='http://localhost:5173/payment/vnpay-return')
        self.app.dependency_overrides[configured_settings] = lambda: self.settings
        self.package = self.request('POST', '/admin/credit-packages', {'name': 'VNPAY credit', 'credits': 200, 'price': 50000}, who='admin', expected=201)

    def checkout(self, identity=None, expected=200):
        return self.request('POST', '/payments/vnpay/checkout', {'request_id': str(identity or uuid4()), 'package_id': self.package['id']}, expected=expected)

    def callback(self, checkout, **changes):
        values = {'vnp_TmnCode': self.settings.tmn_code, 'vnp_TxnRef': UUID(checkout['order_id']).hex,
                  'vnp_Amount': '5000000', 'vnp_ResponseCode': '00', 'vnp_TransactionStatus': '00',
                  'vnp_TransactionNo': '123456789', 'vnp_PayDate': '20261106180000', **changes}
        values['vnp_SecureHash'] = signature(values, self.settings.hash_secret)
        return values

    def ipn(self, params):
        response = self.client.get('/api/payments/vnpay/ipn?' + urlencode(params))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()


class VNPAYApiTests(VNPAYFixture):
    def test_checkout_signs_server_price_in_vnd_times_100_and_reuses_reference(self):
        identity = uuid4()
        first, second = self.checkout(identity), self.checkout(identity)
        self.assertEqual(first, second)
        params = {key: values[0] for key, values in parse_qs(urlsplit(first['payment_url']).query).items()}
        self.assertEqual(params['vnp_Amount'], '5000000')
        self.assertEqual(params['vnp_TxnRef'], identity.hex)
        self.assertEqual(params['vnp_Version'], '2.1.0')
        self.assertIsNotNone(verified_query(params.items(), self.settings))
        self.assertEqual(self.balance(), 1000)
        self.assertNotIn(self.settings.hash_secret, first['payment_url'])
        self.request('POST', '/admin/cash-orders/' + first['order_id'] + '/decision', {'success': True, 'reason': 'Manual override'}, who='head', expected=400)

    def test_valid_return_does_not_credit_and_duplicate_ipn_credits_only_once(self):
        checkout = self.checkout()
        params = self.callback(checkout)
        result = self.client.get('/api/payments/vnpay/return?' + urlencode(params)).json()
        self.assertTrue(result['signature_valid'])
        self.assertFalse(result['credited'])
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(self.ipn(params)['RspCode'], '00')
        self.assertEqual(self.ipn(params)['RspCode'], '02')
        self.assertEqual(self.balance(), 1200)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalTransaction)), 1)
        result = self.client.get('/api/payments/vnpay/return?' + urlencode(params)).json()
        self.assertTrue(result['credited'])

    def test_invalid_signature_tampering_and_duplicate_parameters_cannot_credit(self):
        checkout = self.checkout()
        params = self.callback(checkout)
        self.assertEqual(self.ipn({**params, 'vnp_Amount': '1'})['RspCode'], '97')
        self.assertEqual(self.ipn({**params, 'vnp_SecureHash': '0' * 128})['RspCode'], '97')
        response = self.client.get('/api/payments/vnpay/ipn?' + urlencode(params) + '&vnp_Amount=5000000')
        self.assertEqual(response.json()['RspCode'], '97')
        self.assertEqual(self.balance(), 1000)

    def test_wrong_merchant_unknown_order_and_wrong_signed_amount_are_rejected(self):
        checkout = self.checkout()
        self.assertEqual(self.ipn(self.callback(checkout, vnp_TmnCode='OTHER123'))['RspCode'], '97')
        self.assertEqual(self.ipn(self.callback(checkout, vnp_TxnRef=uuid4().hex))['RspCode'], '01')
        self.assertEqual(self.ipn(self.callback(checkout, vnp_Amount='10000'))['RspCode'], '04')
        self.assertEqual(self.balance(), 1000)

    def test_failed_or_unfinished_payments_never_credit(self):
        checkout = self.checkout()
        pending = self.callback(checkout, vnp_TransactionStatus='01')
        self.assertEqual(self.ipn(pending)['RspCode'], '99')
        self.assertEqual(self.request('GET', '/me/cash-orders')[0]['status'], 'pending')
        failed = self.callback(checkout, vnp_ResponseCode='24', vnp_TransactionStatus='02', vnp_TransactionNo='0')
        self.assertEqual(self.ipn(failed)['RspCode'], '00')
        self.assertEqual(self.request('GET', '/me/cash-orders')[0]['status'], 'failed')
        self.assertEqual(self.balance(), 1000)

    def test_merchant_configuration_missing_returns_503_without_creating_order(self):
        self.app.dependency_overrides[configured_settings] = lambda: None
        self.assertFalse(self.request('GET', '/payments/vnpay/status', who=None)['enabled'])
        self.checkout(expected=503)
        self.assertEqual(self.request('GET', '/me/cash-orders'), [])

    def test_callback_commit_failure_rolls_back_credit_and_allows_retry(self):
        checkout = self.checkout()
        params = self.callback(checkout)
        def fail(_session):
            from sqlalchemy.exc import OperationalError
            raise OperationalError('test', None, Exception('test failure'))
        event.listen(self.factory, 'before_commit', fail)
        try:
            self.assertEqual(self.ipn(params)['RspCode'], '99')
        finally:
            event.remove(self.factory, 'before_commit', fail)
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(self.ipn(params)['RspCode'], '00')
        self.assertEqual(self.balance(), 1200)

    def test_vnpay_minimum_amount_rejects_small_package_without_creating_order(self):
        self.request('PUT', '/admin/credit-packages/' + self.package['id'],
                     {'name': 'Too small for VNPAY', 'credits': 10, 'price': 4999}, who='admin')
        self.checkout(expected=400)
        self.assertEqual(self.request('GET', '/me/cash-orders'), [])
        self.request('PUT', '/admin/credit-packages/' + self.package['id'],
                     {'name': 'VNPAY minimum', 'credits': 10, 'price': 5000}, who='admin')
        result = self.checkout()
        params = parse_qs(urlsplit(result['payment_url']).query)
        self.assertEqual(params['vnp_Amount'], ['500000'])

    def test_checkout_cannot_reuse_someone_elses_order_or_change_snapshot(self):
        checkout = self.checkout()
        self.request('POST', '/payments/vnpay/checkout', {'request_id': checkout['order_id'], 'package_id': self.package['id']}, who='other', expected=400)
        self.request('PUT', '/admin/credit-packages/' + self.package['id'], {'name': 'New price', 'credits': 400, 'price': 90000}, who='admin')
        params = parse_qs(urlsplit(self.checkout(UUID(checkout['order_id']))['payment_url']).query)
        self.assertEqual(params['vnp_Amount'], ['5000000'])
        self.assertEqual(self.ipn(self.callback(checkout))['RspCode'], '00')
        self.assertEqual(self.balance(), 1200)


if __name__ == '__main__':
    unittest.main()
