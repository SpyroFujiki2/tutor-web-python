"""Add an optional full name to user profiles."""
from alembic import op
import sqlalchemy as sa

revision = '0004_user_full_name'
down_revision = '0003_lesson_duration_seconds'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('full_name', sa.String(200), nullable=True))


def downgrade():
    op.drop_column('users', 'full_name')
