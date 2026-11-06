import io
import secrets
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from urllib.error import URLError

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

    def test_probe_only_reads_health_status_and_unsigned_ipn(self):
        with patch.object(check_vnpay, 'probe_json', side_effect=[
            {'status': 'ok'}, {'enabled': True, 'sandbox': True},
            {'RspCode': '97', 'Message': 'Invalid signature'},
        ]) as probe:
            code, output = self.run_check('--probe')
        self.assertEqual(code, 0)
        self.assertEqual([call.args[0] for call in probe.call_args_list], [
            'https://tutor.example/api/ready',
            'https://tutor.example/api/payments/vnpay/status',
            'https://tutor.example/api/payments/vnpay/ipn',
        ])
        self.assertNotIn(self.secret, output)

    def test_probe_failure_is_reported_without_leaking_exception_details(self):
        with patch.object(check_vnpay, 'urlopen', side_effect=URLError(self.secret)):
            code, output = self.run_check('--probe')
        self.assertEqual(code, 1)
        self.assertNotIn(self.secret, output)
        self.assertIn('FAIL: /api/payments/vnpay/ipn', output)


if __name__ == '__main__':
    unittest.main()
