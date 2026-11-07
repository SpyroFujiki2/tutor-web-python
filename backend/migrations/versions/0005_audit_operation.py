"""Preserve create/update distinctions for future audit events."""
from alembic import op
import sqlalchemy as sa

revision = '0005_audit_operation'
down_revision = '0004_user_full_name'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('action_logs', sa.Column('operation', sa.String(10), nullable=True))
    op.create_check_constraint('valid_operation', 'action_logs', "operation IS NULL OR operation IN ('GET','POST','PUT','PATCH','DELETE','OTHER')")


def downgrade():
    op.drop_constraint('valid_operation', 'action_logs', type_='check')
    op.drop_column('action_logs', 'operation')
