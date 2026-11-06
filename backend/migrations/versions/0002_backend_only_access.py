"""Keep application data behind FastAPI authorization, including on Supabase.

The application uses its own JWTs and role checks, not Supabase Auth policies.
Enabling RLS without public policies prevents anon/authenticated Data API access.
The backend database owner/BYPASSRLS role retains its existing SQL access.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_backend_only_access"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

# Frozen names, independent of later model changes or third-party schemas.
TABLES = (
    "action_logs", "attendance", "auth_sessions", "booking", "booking_sessions",
    "booking_settlements", "cash_order", "comment_report", "comments",
    "course_progress", "courses", "credit_package", "disputes",
    "external_transaction", "internal_transaction", "lessons", "messages",
    "payment_method", "posts", "role_requests", "tutoring_package",
    "user_subscriptions", "users", "wallet_snapshots", "wallets",
    "alembic_version",
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
