import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import func, select

from app.core.security import verify_password
from app.models import ActionLog, TutoringPackage, User, Wallet
from app.models.enums import UserRole, UserStatus, WalletType
from scripts import seed_demo
from test_domain_api import DomainApiFixture


class DemoSeedTests(DomainApiFixture):
    def setUp(self):
        super().setUp()
        self.values = seed_demo.new_seed_values()

    def seed(self):
        with self.factory.begin() as session:
            return seed_demo.seed_demo_data(session, self.values)

    def test_all_roles_can_log_in_and_seed_has_zero_balance_wallets_and_three_distinct_prices(self):
        result = self.seed()
        self.assertEqual((result['created_users'], result['created_packages']), (7, 3))
        self.assertEqual({row['role'] for row in result['accounts']}, {role.value for role in UserRole})
        self.assertEqual(len({row['price'] for row in result['packages']}), 3)
        for row in result['packages']:
            self.assertTrue(100000 <= row['price'] <= 500000)
            self.assertTrue(row['is_active'])
        with self.factory() as session:
            logs = json.dumps([row.new_value for row in session.scalars(select(ActionLog))])
            for role in UserRole:
                user = session.get(User, seed_demo.seed_user_id(role))
                password = self.values[f'SEED_{role.name}_PASSWORD']
                self.assertTrue(verify_password(password, user.password_hash)[0])
                self.assertNotIn(password, logs)
                wallets = list(session.scalars(select(Wallet).where(Wallet.user_id == user.id)))
                expected_types = {WalletType.NORMAL}
                if role in {UserRole.TUTOR, UserRole.ADMIN, UserRole.HEAD_ADMIN}:
                    expected_types.add(WalletType.COMMERCIAL)
                self.assertEqual({wallet.type for wallet in wallets}, expected_types)
                self.assertTrue(all(wallet.available_balance == wallet.holding_balance == wallet.debt == 0 for wallet in wallets))
                response = self.client.post('/api/auth/login', json={'email': user.email, 'password': password})
                self.assertEqual(response.status_code, 200)
                me = self.client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + response.json()['access_token']})
                self.assertEqual(me.json()['role'], role.value)

    def test_repeat_keeps_existing_passwords_prices_and_suspended_account(self):
        first = self.seed()
        with self.factory.begin() as session:
            user = session.get(User, seed_demo.seed_user_id(UserRole.MEMBER))
            user.status = UserStatus.SUSPENDED
            saved_hash = user.password_hash
            package = session.get(TutoringPackage, seed_demo.seed_package_id(1))
            package.price, package.is_active = 555555, False
            log_count = session.scalar(select(func.count()).select_from(ActionLog))
        second = self.seed()
        self.assertEqual((second['created_users'], second['created_packages']), (0, 0))
        self.assertEqual(first['accounts'], second['accounts'])
        with self.factory() as session:
            user = session.get(User, seed_demo.seed_user_id(UserRole.MEMBER))
            self.assertEqual(user.status, UserStatus.SUSPENDED)
            self.assertEqual(user.password_hash, saved_hash)
            package = session.get(TutoringPackage, seed_demo.seed_package_id(1))
            self.assertEqual((package.price, package.is_active), (555555, False))
            self.assertEqual(session.scalar(select(func.count()).select_from(ActionLog)), log_count)

    def test_email_collision_rolls_back_without_granting_role_to_existing_user(self):
        with self.factory.begin() as session:
            identity = uuid4()
            session.add(User(id=identity, email=self.values['SEED_ADMIN_EMAIL'],
                             role=UserRole.MEMBER, status=UserStatus.ACTIVE))
            baseline = session.scalar(select(func.count()).select_from(User))
        with self.assertRaisesRegex(ValueError, 'không ghi đè hoặc nâng quyền'):
            self.seed()
        with self.factory() as session:
            self.assertEqual(session.get(User, identity).role, UserRole.MEMBER)
            self.assertEqual(session.scalar(select(func.count()).select_from(User)), baseline)
            self.assertIsNone(session.get(User, seed_demo.seed_user_id(UserRole.HEAD_ADMIN)))
            self.assertEqual(session.scalar(select(func.count()).select_from(TutoringPackage)), 0)

    def test_cli_dry_run_does_not_save_credentials_or_database_records(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / '.env.seed'
            with patch.object(seed_demo, 'CREDENTIALS_PATH', target), \
                    patch.object(seed_demo, 'get_database_settings'), \
                    patch.object(seed_demo, 'create_database_engine', return_value=self.engine), \
                    patch.object(self.engine, 'dispose'), redirect_stdout(io.StringIO()):
                seed_demo.main(['--dry-run'])
            self.assertFalse(target.exists())
        with self.factory() as session:
            self.assertIsNone(session.get(User, seed_demo.seed_user_id(UserRole.HEAD_ADMIN)))
            self.assertEqual(session.scalar(select(func.count()).select_from(TutoringPackage)), 0)

    def test_credentials_are_reused_without_printing_or_changing_file(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / '.env.seed'
            output = io.StringIO()
            with redirect_stdout(output):
                first = seed_demo.load_seed_values(target)
                original = target.read_bytes()
                second = seed_demo.load_seed_values(target)
            self.assertEqual(first, second)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(output.getvalue(), '')

    def test_missing_credentials_file_does_not_replace_existing_account_passwords(self):
        self.seed()
        with TemporaryDirectory() as directory:
            target = Path(directory) / '.env.seed'
            with patch.object(seed_demo, 'CREDENTIALS_PATH', target), \
                    patch.object(seed_demo, 'get_database_settings'), \
                    patch.object(seed_demo, 'create_database_engine', return_value=self.engine), \
                    patch.object(self.engine, 'dispose'), redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, 'khôi phục file'):
                    seed_demo.main([])
            self.assertFalse(target.exists())
