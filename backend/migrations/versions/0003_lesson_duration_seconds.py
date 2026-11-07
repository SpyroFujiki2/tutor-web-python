"""Store video metadata duration in seconds, without rounding to minutes."""
from alembic import op
import sqlalchemy as sa

revision = '0003_lesson_duration_seconds'
down_revision = '0002_backend_only_access'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('lessons', sa.Column('duration_seconds', sa.Integer(), nullable=True))
    op.create_check_constraint('positive_duration_seconds', 'lessons', 'duration_seconds IS NULL OR duration_seconds > 0')


def downgrade():
    op.drop_constraint('positive_duration_seconds', 'lessons', type_='check')
    op.drop_column('lessons', 'duration_seconds')
