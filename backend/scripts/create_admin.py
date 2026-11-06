"""Create a first administrator explicitly; never ships default credentials.

Run from backend: python -m scripts.create_admin --email admin@example.com
"""

import argparse
from getpass import getpass

from sqlalchemy import select

from app.core.config import get_database_settings
from app.core.database import create_database_engine, create_session_factory
from app.models import User
from app.models.enums import UserRole
from app.modules.common import audit, require
from app.modules.finance.payments import platform_wallet
from app.modules.users.accounts import register_user
from app.schemas.auth import RegisterRequest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    args = parser.parse_args()
    password = getpass('New administrator password (8+ characters): ')
    require(password == getpass('Confirm password: '), 'Passwords do not match')
    payload = RegisterRequest(email=args.email, password=password)
    engine = create_database_engine(get_database_settings())
    try:
        with create_session_factory(engine).begin() as session:
            # This bootstrap command cannot grant privileges to an existing account.
            require(session.scalar(select(User.id).where(User.role == UserRole.HEAD_ADMIN).limit(1)) is None,
                    'A head administrator already exists; use the reviewed role-request workflow')
            user = register_user(session, payload.email, payload.password.get_secret_value())
            user.role = UserRole.HEAD_ADMIN
            platform_wallet(session)
            audit(session, user, user, 'admin.bootstrap', after={'role': user.role}, reason='Explicit local bootstrap')
        print('Administrator created. Sign in through the website.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
