"""Create seven demo role accounts and three randomly priced tutoring packages.

Run from backend: python -m scripts.seed_demo [--dry-run]
Credentials and the initial prices are kept in the git-ignored root .env.seed.
"""

import argparse
import secrets
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from dotenv import dotenv_values
from pydantic import ValidationError
from sqlalchemy import select, text

from app.core.config import ROOT_DIR, get_database_settings
from app.core.database import create_database_engine, create_session_factory
from app.core.security import hash_password
from app.models import TutoringPackage, User
from app.models.enums import UserRole, UserStatus, WalletType
from app.modules.common import add, audit, now, require
from app.modules.finance.wallet import create_wallet, platform_wallet
from app.schemas.auth import RegisterRequest

SEED_NAMESPACE = uuid5(NAMESPACE_URL, 'tutor-web-python/demo-seed/v1')
CREDENTIALS_PATH = ROOT_DIR / '.env.seed'
PACKAGE_NAMES = ('Gia sư Cơ bản (mẫu)', 'Gia sư Nâng cao (mẫu)', 'Gia sư Chuyên sâu (mẫu)')


def seed_user_id(role):
    return uuid5(SEED_NAMESPACE, 'user:' + role.value)


def seed_package_id(index):
    return uuid5(SEED_NAMESPACE, 'tutoring-package:' + str(index))


def new_seed_values():
    values = {}
    for role in UserRole:
        values[f'SEED_{role.name}_EMAIL'] = f'{role.value}@tutor.example.com'
        values[f'SEED_{role.name}_PASSWORD'] = secrets.token_urlsafe(18)
    for index, price in enumerate(sorted(secrets.SystemRandom().sample(range(100000, 500001, 10000), 3)), 1):
        values[f'SEED_TUTOR_PACKAGE_{index}_PRICE'] = str(price)
    return values


def load_seed_values(path: Path, *, dry_run=False):
    if path.exists():
        return dict(dotenv_values(path, interpolate=False))
    values = new_seed_values()
    if not dry_run:
        try:
            with path.open('x', encoding='utf-8') as stream:
                stream.write('# Local demo credentials. Do not commit or share this file.\n')
                stream.write('# Reused on subsequent seeds; existing users/passwords/prices are not reset.\n')
                for key, value in values.items():
                    stream.write(f"{key}='{value}'\n")
        except FileExistsError:
            return dict(dotenv_values(path, interpolate=False))
    return values


def seed_demo_data(session, values):
    # Serialize repeated CLI runs without changing business tables or migrations.
    if session.bind.dialect.name == 'postgresql':
        session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': 6076851562588915013})
    accounts = {}
    for role in UserRole:
        email = values.get(f'SEED_{role.name}_EMAIL')
        password = values.get(f'SEED_{role.name}_PASSWORD')
        require(bool(email and password), 'Seed thiếu email/mật khẩu; kiểm tra .env.seed')
        try:
            accounts[role] = RegisterRequest(email=email, password=password)
        except ValidationError:
            raise ValueError('Email hoặc mật khẩu trong .env.seed không hợp lệ') from None
    try:
        prices = [int(values[f'SEED_TUTOR_PACKAGE_{index}_PRICE']) for index in range(1, 4)]
    except (KeyError, TypeError, ValueError):
        raise ValueError('Seed thiếu giá hợp lệ; kiểm tra .env.seed') from None
    require(len(set(prices)) == 3 and all(100000 <= price <= 500000 and price % 10000 == 0 for price in prices),
            'Giá seed cần khác nhau, từ 100.000 đến 500.000 credit, bước 10.000')
    require(len({str(item.email).lower() for item in accounts.values()}) == len(UserRole),
            'Email tài khoản seed phải khác nhau')

    users = {}
    created_users = []
    order = [UserRole.HEAD_ADMIN] + [role for role in UserRole if role != UserRole.HEAD_ADMIN]
    for role in order:
        payload = accounts[role]
        email = str(payload.email).lower()
        identity = seed_user_id(role)
        user = session.get(User, identity, with_for_update=True)
        if user is None:
            require(session.scalar(select(User.id).where(User.email == email)) is None,
                    f'Email seed cho {role.value} đã thuộc tài khoản khác; không ghi đè hoặc nâng quyền')
            user = add(session, User, id=identity, email=email,
                       password_hash=hash_password(payload.password.get_secret_value()),
                       role=role, status=UserStatus.ACTIVE, created_at=now())
            created_users.append(role)
        else:
            require(user.email == email and user.role == role,
                    f'Tài khoản seed {role.value} đã thay đổi; không ghi đè email/role')
        users[role] = user
        # Do not reactivate accounts or wallets changed after the initial seed.
        if user.status == UserStatus.ACTIVE:
            create_wallet(session, user.id, WalletType.NORMAL)
            if role in {UserRole.TUTOR, UserRole.ADMIN, UserRole.HEAD_ADMIN}:
                create_wallet(session, user.id, WalletType.COMMERCIAL)

    head = users[UserRole.HEAD_ADMIN]
    require(head.status == UserStatus.ACTIVE, 'Head admin seed đang bị khóa; không tự kích hoạt lại')
    for role in created_users:
        audit(session, head, users[role], 'user.seed', after={'role': role, 'status': UserStatus.ACTIVE},
              reason='Explicit local demo seed: one account per role')
    platform_wallet(session)

    packages = []
    created_packages = 0
    for index, (name, price) in enumerate(zip(PACKAGE_NAMES, prices), 1):
        row = session.get(TutoringPackage, seed_package_id(index), with_for_update=True)
        if row is None:
            row = add(session, TutoringPackage, id=seed_package_id(index), name=name, price=price, is_active=True)
            audit(session, head, row, 'tutoring_package.save',
                  after={'name': name, 'price': price, 'is_active': True}, reason='Explicit local demo seed')
            created_packages += 1
        packages.append({'id': str(row.id), 'name': row.name, 'price': row.price, 'is_active': row.is_active})
    return {
        'created_users': len(created_users), 'created_packages': created_packages,
        'accounts': [{'id': str(users[role].id), 'email': users[role].email, 'role': role.value} for role in UserRole],
        'packages': packages,
    }


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Validate and roll back without saving credentials')
    args = parser.parse_args(argv)
    engine = create_database_engine(get_database_settings())
    try:
        with create_session_factory(engine)() as session:
            if not args.dry_run and not CREDENTIALS_PATH.exists():
                existing = session.scalar(select(User.id).where(User.id.in_(
                    [seed_user_id(role) for role in UserRole])).limit(1))
                require(existing is None, 'Tài khoản seed đã tồn tại nhưng thiếu .env.seed; khôi phục file thay vì sinh lại mật khẩu')
            values = load_seed_values(CREDENTIALS_PATH, dry_run=args.dry_run)
            result = seed_demo_data(session, values)
            if args.dry_run:
                session.rollback()
            else:
                session.commit()
        label = 'Dry run (rolled back)' if args.dry_run else 'Demo seed complete'
        print(f"{label}: {result['created_users']} accounts and {result['created_packages']} tutoring packages created.")
        for row in result['accounts']:
            print(f"  {row['role']}: {row['email']}")
        for row in result['packages']:
            print(f"  {row['name']}: {row['price']:,} credit")
        if not args.dry_run:
            print(f'Credentials: {CREDENTIALS_PATH} (passwords are not printed).')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
