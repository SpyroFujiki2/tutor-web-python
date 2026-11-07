import io
import secrets
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qsl, urlsplit
from app.core.vnpay import get_vnpay_settings, verified_query

from scripts import check_vnpay


class VNPAYSetupTests(unittest.TestCase):
    def setUp(self):
        self.secret = secrets.token_hex(32)
        self.values = {
            'VNPAY_TMN_CODE': 'TEST1234', 'VNPAY_HASH_SECRET': self.secret,
            'VNPAY_RETURN_URL': 'https://tutor.example/payment/vnpay-return',
        }
        self.enterContext(patch.dict('os.environ', {}, clear=True))
        self.enterContext(patch.object(check_vnpay, 'dotenv_values', return_value=self.values))
        self.enterContext(patch('app.core.vnpay.dotenv_values', return_value=self.values))

    def run_check(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = check_vnpay.main(list(args))
        return code, output.getvalue()

    def test_configuration_shows_callback_urls_without_revealing_credentials(self):
        code, output = self.run_check()
        self.assertEqual(code, 0)
        self.assertIn('https://tutor.example/api/payments/vnpay/ipn', output)
        self.assertNotIn(self.secret, output)
        self.assertNotIn(self.values['VNPAY_TMN_CODE'], output)

    def test_missing_keys_or_localhost_return_are_not_ready_for_public_ipn(self):
        self.values.pop('VNPAY_HASH_SECRET')
        code, output = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('Missing VNPAY_HASH_SECRET', output)
        self.values['VNPAY_HASH_SECRET'] = self.secret
        self.values['VNPAY_RETURN_URL'] = 'http://localhost:5173/payment/vnpay-return'
        code, output = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('public HTTPS', output)

    def test_probe_checks_deployed_signing_keys_without_using_a_real_order(self):
        with patch.object(check_vnpay, 'probe_json', side_effect=[
            {'status': 'ok'}, {'enabled': True, 'sandbox': True},
            {'RspCode': '97', 'Message': 'Invalid signature'},
            {'RspCode': '01', 'Message': 'Order not found'},
        ]) as probe:
            code, output = self.run_check('--probe')
        self.assertEqual(code, 0)
        self.assertEqual([call.args[0] for call in probe.call_args_list[:3]], [
            'https://tutor.example/api/ready',
            'https://tutor.example/api/payments/vnpay/status',
            'https://tutor.example/api/payments/vnpay/ipn',
        ])
        signed = probe.call_args_list[3].args[0]
        self.assertIsNotNone(verified_query(parse_qsl(urlsplit(signed).query), get_vnpay_settings()))
        self.assertIn('signed IPN probe', output)
        self.assertNotIn(self.secret, output)

    def test_probe_failure_is_reported_without_leaking_exception_details(self):
        with patch.object(check_vnpay, 'urlopen', side_effect=URLError(self.secret)):
            code, output = self.run_check('--probe')
        self.assertEqual(code, 1)
        self.assertNotIn(self.secret, output)
        self.assertIn('FAIL: /api/payments/vnpay/ipn', output)

    def test_unsigned_probe_passing_does_not_hide_mismatched_deployed_credentials(self):
        with patch.object(check_vnpay, 'probe_json', side_effect=[
            {'status': 'ok'}, {'enabled': True, 'sandbox': True},
            {'RspCode': '97'}, {'RspCode': '97'},
        ]):
            code, output = self.run_check('--probe')
        self.assertEqual(code, 1)
        self.assertIn('FAIL: signed IPN probe', output)
        self.assertNotIn(self.secret, output)


if __name__ == '__main__':
    unittest.main()
