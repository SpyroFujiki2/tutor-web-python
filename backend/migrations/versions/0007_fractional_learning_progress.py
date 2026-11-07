"""Allow learning completion without a grade and require explicit assignment completion."""
from alembic import op
import sqlalchemy as sa

revision = '0007_learning_progress'
down_revision = '0006_database_audit_operation'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('attendance', sa.Column('assignment_completed', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.drop_constraint('completion_requires_result', 'course_progress', type_='check')
    op.create_check_constraint('completion_requires_result', 'course_progress',
        '(progress_percent < 100 AND result IS NULL AND completed_at IS NULL) OR '
        '(progress_percent = 100 AND completed_at IS NOT NULL AND '
        '((result IS NULL AND final_score IS NULL) OR (result IS NOT NULL AND final_score IS NOT NULL)))')


def downgrade():
    op.execute('UPDATE course_progress SET progress_percent = 99.99, completed_at = NULL WHERE progress_percent = 100 AND (result IS NULL OR final_score IS NULL)')
    op.drop_constraint('completion_requires_result', 'course_progress', type_='check')
    op.create_check_constraint('completion_requires_result', 'course_progress',
        '(progress_percent < 100 AND result IS NULL AND completed_at IS NULL) OR '
        '(progress_percent = 100 AND result IS NOT NULL AND final_score IS NOT NULL AND completed_at IS NOT NULL)')
    op.drop_column('attendance', 'assignment_completed')
