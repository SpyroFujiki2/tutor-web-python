"""Use database operation categories while retaining older audit values."""
from alembic import op

revision = '0006_database_audit_operation'
down_revision = '0005_audit_operation'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('valid_operation', 'action_logs', type_='check')
    op.create_check_constraint('valid_operation', 'action_logs', "operation IS NULL OR operation IN ('INSERT','SELECT','UPDATE','DELETE','OTHER','GET','POST','PUT','PATCH')")


def downgrade():
    op.execute("UPDATE action_logs SET operation = CASE operation WHEN 'INSERT' THEN 'POST' WHEN 'SELECT' THEN 'GET' WHEN 'UPDATE' THEN 'PATCH' ELSE operation END")
    op.drop_constraint('valid_operation', 'action_logs', type_='check')
    op.create_check_constraint('valid_operation', 'action_logs', "operation IS NULL OR operation IN ('GET','POST','PUT','PATCH','DELETE','OTHER')")
