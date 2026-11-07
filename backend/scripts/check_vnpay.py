"""Check VNPAY configuration and optional HTTP wiring without creating payments."""

import argparse
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from dotenv import dotenv_values

from app.core.config import ROOT_DIR
from app.core.vnpay import get_vnpay_settings, signature


def probe_json(url):
    request = Request(url, headers={'Accept': 'application/json'})
    try:
        with urlopen(request, timeout=10) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError('HTTP endpoint must return 200 without redirects')
            return json.loads(response.read(65536))
    except (HTTPError, URLError, OSError, ValueError):
        # Exceptions can contain request details. Do not expose their contents.
        raise ValueError('Endpoint unavailable or response is not valid JSON') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true', help='Check public API/IPN without creating a transaction')
    args = parser.parse_args(argv)
    values = {
        **dotenv_values(ROOT_DIR / '.env', encoding='utf-8-sig'),
        **dotenv_values(ROOT_DIR / '.env.local', encoding='utf-8-sig'),
        **os.environ,
    }
    missing = [name for name in ('VNPAY_TMN_CODE', 'VNPAY_HASH_SECRET') if not values.get(name)]
    try:
        settings = get_vnpay_settings()
    except ValueError:
        settings = None
        print('FAIL: Invalid VNPAY configuration. Check .env; values are not printed.')
    if missing:
        print('FAIL: Missing ' + ', '.join(missing))
    if settings:
        print('OK: Merchant configuration loaded; credentials are hidden.')
        print('Mode: ' + ('sandbox' if 'sandbox.' in settings.payment_url else 'production'))
    return_url = settings.return_url if settings else values.get('VNPAY_RETURN_URL', '')
    parsed = urlsplit(return_url or '')
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        print('FAIL: Set a public HTTPS VNPAY_RETURN_URL before registering IPN.')
        return 1
    origin = f'{parsed.scheme}://{parsed.netloc}'
    print('Return URL: ' + return_url)
    print('IPN URL (register with VNPAY): ' + origin + '/api/payments/vnpay/ipn')
    checks = [settings is not None]
    if args.probe:
        expectations = (
            ('/api/ready', 'status', 'ok'),
            ('/api/payments/vnpay/status', 'enabled', True),
            ('/api/payments/vnpay/ipn', 'RspCode', '97'),
        )
        for path, key, expected in expectations:
            try:
                result = probe_json(origin + path)
                ok = isinstance(result, dict) and result.get(key) == expected
            except ValueError:
                ok = False
            checks.append(ok)
            print(('OK: ' if ok else 'FAIL: ') + path)
        print('IPN probe is unsigned and must be rejected with RspCode=97; no wallet is changed.')
        if settings:
            params = {'vnp_TmnCode': settings.tmn_code, 'vnp_TxnRef': uuid4().hex}
            params['vnp_SecureHash'] = signature(params, settings.hash_secret)
            try:
                result = probe_json(origin + '/api/payments/vnpay/ipn?' + urlencode(params))
                ok = isinstance(result, dict) and result.get('RspCode') == '01'
            except ValueError:
                ok = False
            checks.append(ok)
            print(('OK: ' if ok else 'FAIL: ') + 'signed IPN probe (nonexistent order; expected RspCode=01)')
            if not ok:
                print('Check Vercel environment scope, merchant/key values, then redeploy. The local and deployed settings may differ.')
    print('This check does not confirm a real sandbox payment or VNPAY IPN registration.')
    return 0 if all(checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
