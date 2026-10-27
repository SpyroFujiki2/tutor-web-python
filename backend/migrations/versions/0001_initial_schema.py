"""Initial 25-table schema, frozen from the DBML models plus AuthSession.

Enums are created once and shared by columns without per-table CREATE TYPE.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    postgresql.ENUM('visible', 'hidden', name='course_status', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('guest', 'member', 'student', 'trainee_tutor', 'tutor', 'admin', 'head_admin', name='user_role', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('active', 'suspended', 'banned', name='user_status', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('pending', 'approved', 'rejected', name='request_status', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('booking', 'course', name='service_type', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('active', 'expired', 'cancelled', name='subscription_status', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('normal', 'commercial', name='wallet_type', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('pending', 'confirmed', 'assigned', 'completed', 'cancelled', 'refunded', 'disputing', name='booking_status', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('in', 'out', name='cash_order_type', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('pending', 'success', 'failed', name='cash_order_status', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('excellent', 'good', 'failed', name='course_result', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('recharge', 'payment', 'revenue', 'withdraw', 'refund', name='transaction_type', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('scheduled', 'completed', 'cancelled', name='booking_session_status', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('held', 'released', 'refunded', name='escrow_status', create_type=False).create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('refund_full', 'refund_partial', 'rejected', name='dispute_verdict', create_type=False).create(op.get_bind(), checkfirst=False)
    op.create_table('courses',
    sa.Column('status', postgresql.ENUM('visible', 'hidden', name='course_status', create_type=False), server_default=sa.text("'visible'"), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('price', sa.Integer(), nullable=True),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('is_live', sa.Boolean(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_courses'))
    )
    op.create_table('credit_package',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('credits', sa.Integer(), nullable=True),
    sa.Column('price', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_credit_package'))
    )
    op.create_table('tutoring_package',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('price', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tutoring_package'))
    )
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('password_hash', sa.String(), nullable=True),
    sa.Column('role', postgresql.ENUM('guest', 'member', 'student', 'trainee_tutor', 'tutor', 'admin', 'head_admin', name='user_role', create_type=False), nullable=True),
    sa.Column('status', postgresql.ENUM('active', 'suspended', 'banned', name='user_status', create_type=False), server_default=sa.text("'active'"), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('last_active_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('action_logs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('admin_id', sa.Uuid(), nullable=True),
    sa.Column('target_user_id', sa.Uuid(), nullable=True),
    sa.Column('target_type', sa.String(), nullable=True),
    sa.Column('target_id', sa.Uuid(), nullable=True),
    sa.Column('action_code', sa.String(), nullable=True),
    sa.Column('old_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['admin_id'], ['users.id'], name=op.f('fk_action_logs_admin_id_users')),
    sa.ForeignKeyConstraint(['target_user_id'], ['users.id'], name=op.f('fk_action_logs_target_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_action_logs'))
    )
    op.create_index(op.f('ix_action_logs_created_at'), 'action_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_action_logs_target_id'), 'action_logs', ['target_id'], unique=False)
    op.create_index(op.f('ix_action_logs_target_user_id'), 'action_logs', ['target_user_id'], unique=False)
    op.create_table('auth_sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('refresh_token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('expires_at > created_at', name=op.f('ck_auth_sessions_valid_session_lifetime')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_auth_sessions_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_sessions'))
    )
    op.create_index(op.f('ix_auth_sessions_expires_at'), 'auth_sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_auth_sessions_user_id_revoked_at'), 'auth_sessions', ['user_id', 'revoked_at'], unique=False)
    op.create_table('lessons',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('course_id', sa.Uuid(), nullable=False),
    sa.Column('order_idx', sa.Integer(), nullable=False),
    sa.Column('media_url', sa.String(), nullable=True),
    sa.Column('assignment_url', sa.String(), nullable=True),
    sa.Column('session_count', sa.Integer(), nullable=True),
    sa.Column('duration_minutes', sa.Integer(), nullable=True),
    sa.CheckConstraint('duration_minutes IS NULL OR duration_minutes > 0', name=op.f('ck_lessons_positive_duration_minutes')),
    sa.CheckConstraint('session_count IS NULL OR session_count > 0', name=op.f('ck_lessons_positive_session_count')),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_lessons_course_id_courses')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lessons')),
    sa.UniqueConstraint('course_id', 'order_idx', name=op.f('uq_lessons_course_id_order_idx')),
    sa.UniqueConstraint('id', 'course_id', name=op.f('uq_lessons_id_course_id'))
    )
    op.create_table('payment_method',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('bank_name', sa.String(), nullable=True),
    sa.Column('account_number', sa.String(), nullable=True),
    sa.Column('account_holder_name', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_payment_method_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_method')),
    sa.UniqueConstraint('user_id', 'account_number', name=op.f('uq_payment_method_user_id_account_number'))
    )
    op.create_table('posts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('author_id', sa.Uuid(), nullable=True),
    sa.Column('author_nickname', sa.String(), nullable=True),
    sa.Column('author_avatar_url', sa.String(), nullable=True),
    sa.Column('title', sa.String(), nullable=True),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('min_role_level', sa.Integer(), nullable=True),
    sa.Column('is_hidden', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], name=op.f('fk_posts_author_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_posts'))
    )
    op.create_table('role_requests',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('current_role_at_request', postgresql.ENUM('guest', 'member', 'student', 'trainee_tutor', 'tutor', 'admin', 'head_admin', name='user_role', create_type=False), nullable=True),
    sa.Column('question_set', sa.Integer(), nullable=True),
    sa.Column('answer_url', sa.String(), nullable=True),
    sa.Column('request_note', sa.Text(), nullable=True),
    sa.Column('status', postgresql.ENUM('pending', 'approved', 'rejected', name='request_status', create_type=False), server_default=sa.text("'pending'"), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.Column('admin_id', sa.Uuid(), nullable=True),
    sa.Column('admin_note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['admin_id'], ['users.id'], name=op.f('fk_role_requests_admin_id_users')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_role_requests_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_role_requests'))
    )
    op.create_table('user_subscriptions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('type', postgresql.ENUM('booking', 'course', name='service_type', create_type=False), nullable=False),
    sa.Column('title_at_purchase', sa.String(), nullable=True),
    sa.Column('price_at_purchase', sa.Integer(), nullable=True),
    sa.Column('status', postgresql.ENUM('active', 'expired', 'cancelled', name='subscription_status', create_type=False), server_default=sa.text("'active'"), nullable=True),
    sa.Column('activated_at', sa.DateTime(), nullable=False),
    sa.Column('expired_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_subscriptions_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_subscriptions'))
    )
    op.create_index(op.f('ix_user_subscriptions_type'), 'user_subscriptions', ['type'], unique=False)
    op.create_index(op.f('ix_user_subscriptions_user_id_status'), 'user_subscriptions', ['user_id', 'status'], unique=False)
    op.create_table('wallets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('type', postgresql.ENUM('normal', 'commercial', name='wallet_type', create_type=False), nullable=False),
    sa.Column('available_balance', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('holding_balance', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('debt', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('commission_rate', sa.Integer(), nullable=True),
    sa.Column('contract_id', sa.String(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint("type = 'commercial' OR (holding_balance = 0 AND debt = 0 AND commission_rate IS NULL AND contract_id IS NULL)", name=op.f('ck_wallets_normal_wallet_fields')),
    sa.CheckConstraint('available_balance >= 0 AND holding_balance >= 0 AND debt >= 0', name=op.f('ck_wallets_nonnegative_balances')),
    sa.CheckConstraint('commission_rate IS NULL OR (commission_rate >= 0 AND commission_rate <= 100)', name=op.f('ck_wallets_commission_range')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_wallets_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_wallets')),
    sa.UniqueConstraint('user_id', 'type', name=op.f('uq_wallets_user_id_type'))
    )
    op.create_table('booking',
    sa.Column('subject', sa.String(), nullable=True),
    sa.Column('requirements', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('subscription_id', sa.Uuid(), nullable=True),
    sa.Column('package_id', sa.Uuid(), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('tutor_id', sa.Uuid(), nullable=True),
    sa.Column('status', postgresql.ENUM('pending', 'confirmed', 'assigned', 'completed', 'cancelled', 'refunded', 'disputing', name='booking_status', create_type=False), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('last_updated', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['users.id'], name=op.f('fk_booking_customer_id_users')),
    sa.ForeignKeyConstraint(['package_id'], ['tutoring_package.id'], name=op.f('fk_booking_package_id_tutoring_package')),
    sa.ForeignKeyConstraint(['subscription_id'], ['user_subscriptions.id'], name=op.f('fk_booking_subscription_id_user_subscriptions')),
    sa.ForeignKeyConstraint(['tutor_id'], ['users.id'], name=op.f('fk_booking_tutor_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_booking')),
    sa.UniqueConstraint('subscription_id', name=op.f('uq_booking_subscription_id'))
    )
    op.create_index(op.f('ix_booking_created_at'), 'booking', ['created_at'], unique=False)
    op.create_index(op.f('ix_booking_customer_id_status'), 'booking', ['customer_id', 'status'], unique=False)
    op.create_index(op.f('ix_booking_status'), 'booking', ['status'], unique=False)
    op.create_index(op.f('ix_booking_tutor_id_status'), 'booking', ['tutor_id', 'status'], unique=False)
    op.create_table('cash_order',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('wallet_id', sa.Uuid(), nullable=True),
    sa.Column('order_type', postgresql.ENUM('in', 'out', name='cash_order_type', create_type=False), nullable=True),
    sa.Column('package_id', sa.Uuid(), nullable=True),
    sa.Column('amount_vnd', sa.Integer(), nullable=True),
    sa.Column('credit_amount', sa.Integer(), nullable=True),
    sa.Column('status', postgresql.ENUM('pending', 'success', 'failed', name='cash_order_status', create_type=False), nullable=True),
    sa.Column('bank_info', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['package_id'], ['credit_package.id'], name=op.f('fk_cash_order_package_id_credit_package')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_cash_order_user_id_users')),
    sa.ForeignKeyConstraint(['wallet_id'], ['wallets.id'], name=op.f('fk_cash_order_wallet_id_wallets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cash_order'))
    )
    op.create_table('comments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('post_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('parent_id', sa.Uuid(), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('is_hidden', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint('parent_id IS NULL OR parent_id <> id', name=op.f('ck_comments_parent_not_self')),
    sa.ForeignKeyConstraint(['parent_id', 'post_id'], ['comments.id', 'comments.post_id'], name=op.f('fk_comments_parent_id_post_id_comments')),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], name=op.f('fk_comments_post_id_posts')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_comments_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_comments')),
    sa.UniqueConstraint('id', 'post_id', name=op.f('uq_comments_id_post_id'))
    )
    op.create_index(op.f('ix_comments_parent_id_post_id'), 'comments', ['parent_id', 'post_id'], unique=False)
    op.create_table('course_progress',
    sa.Column('subscription_id', sa.Uuid(), nullable=False),
    sa.Column('course_id', sa.Uuid(), nullable=False),
    sa.Column('progress_percent', sa.Numeric(precision=5, scale=2), server_default=sa.text('0'), nullable=False),
    sa.Column('attendance_ratio', sa.Numeric(precision=5, scale=4), nullable=True),
    sa.Column('midterm_score', sa.Integer(), nullable=True),
    sa.Column('endterm_score', sa.Integer(), nullable=True),
    sa.Column('practice_score', sa.Integer(), nullable=True),
    sa.Column('final_score', sa.Integer(), nullable=True),
    sa.Column('result', postgresql.ENUM('excellent', 'good', 'failed', name='course_result', create_type=False), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('(progress_percent < 100 AND result IS NULL AND completed_at IS NULL) OR (progress_percent = 100 AND result IS NOT NULL AND final_score IS NOT NULL AND completed_at IS NOT NULL)', name=op.f('ck_course_progress_completion_requires_result')),
    sa.CheckConstraint('attendance_ratio IS NULL OR (attendance_ratio >= 0 AND attendance_ratio <= 1)', name=op.f('ck_course_progress_attendance_ratio_range')),
    sa.CheckConstraint('progress_percent >= 0 AND progress_percent <= 100', name=op.f('ck_course_progress_progress_range')),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_course_progress_course_id_courses')),
    sa.ForeignKeyConstraint(['subscription_id'], ['user_subscriptions.id'], name=op.f('fk_course_progress_subscription_id_user_subscriptions')),
    sa.PrimaryKeyConstraint('subscription_id', name=op.f('pk_course_progress')),
    sa.UniqueConstraint('subscription_id', 'course_id', name=op.f('uq_course_progress_subscription_id_course_id'))
    )
    op.create_index(op.f('ix_course_progress_course_id'), 'course_progress', ['course_id'], unique=False)
    op.create_table('internal_transaction',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('source_wallet_id', sa.Uuid(), nullable=False),
    sa.Column('destination_wallet_id', sa.Uuid(), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=True),
    sa.Column('type', postgresql.ENUM('recharge', 'payment', 'revenue', 'withdraw', 'refund', name='transaction_type', create_type=False), nullable=True),
    sa.Column('subscription_id', sa.Uuid(), nullable=True),
    sa.Column('source_balance_before', sa.Integer(), nullable=True),
    sa.Column('source_balance_after', sa.Integer(), nullable=True),
    sa.Column('destination_balance_before', sa.Integer(), nullable=True),
    sa.Column('destination_balance_after', sa.Integer(), nullable=True),
    sa.Column('checksum', sa.String(), nullable=True),
    sa.Column('created_by_admin_id', sa.Uuid(), nullable=True),
    sa.Column('ref_log_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_admin_id'], ['users.id'], name=op.f('fk_internal_transaction_created_by_admin_id_users')),
    sa.ForeignKeyConstraint(['destination_wallet_id'], ['wallets.id'], name=op.f('fk_internal_transaction_destination_wallet_id_wallets')),
    sa.ForeignKeyConstraint(['ref_log_id'], ['action_logs.id'], name=op.f('fk_internal_transaction_ref_log_id_action_logs')),
    sa.ForeignKeyConstraint(['source_wallet_id'], ['wallets.id'], name=op.f('fk_internal_transaction_source_wallet_id_wallets')),
    sa.ForeignKeyConstraint(['subscription_id'], ['user_subscriptions.id'], name=op.f('fk_internal_transaction_subscription_id_user_subscriptions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_internal_transaction'))
    )
    op.create_index(op.f('ix_internal_transaction_created_at'), 'internal_transaction', ['created_at'], unique=False)
    op.create_index(op.f('ix_internal_transaction_destination_wallet_id'), 'internal_transaction', ['destination_wallet_id'], unique=False)
    op.create_index(op.f('ix_internal_transaction_source_wallet_id'), 'internal_transaction', ['source_wallet_id'], unique=False)
    op.create_index(op.f('ix_internal_transaction_subscription_id'), 'internal_transaction', ['subscription_id'], unique=False)
    op.create_table('wallet_snapshots',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('wallet_id', sa.Uuid(), nullable=True),
    sa.Column('snapshot_date', sa.Date(), nullable=True),
    sa.Column('balance_snap', sa.BigInteger(), nullable=True),
    sa.Column('holding_snap', sa.BigInteger(), nullable=True),
    sa.Column('available_snap', sa.BigInteger(), nullable=True),
    sa.ForeignKeyConstraint(['wallet_id'], ['wallets.id'], name=op.f('fk_wallet_snapshots_wallet_id_wallets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_wallet_snapshots')),
    sa.UniqueConstraint('wallet_id', 'snapshot_date', name=op.f('uq_wallet_snapshots_wallet_id_snapshot_date'))
    )
    op.create_table('attendance',
    sa.Column('subscription_id', sa.Uuid(), nullable=False),
    sa.Column('course_id', sa.Uuid(), nullable=False),
    sa.Column('lesson_id', sa.Uuid(), nullable=False),
    sa.Column('is_absent', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('duration_watched', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.CheckConstraint('duration_watched >= 0', name=op.f('ck_attendance_nonnegative_duration_watched')),
    sa.ForeignKeyConstraint(['lesson_id', 'course_id'], ['lessons.id', 'lessons.course_id'], name=op.f('fk_attendance_lesson_id_course_id_lessons')),
    sa.ForeignKeyConstraint(['subscription_id', 'course_id'], ['course_progress.subscription_id', 'course_progress.course_id'], name=op.f('fk_attendance_subscription_id_course_id_course_progress')),
    sa.PrimaryKeyConstraint('subscription_id', 'lesson_id', name=op.f('pk_attendance'))
    )
    op.create_table('booking_sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('booking_id', sa.Uuid(), nullable=False),
    sa.Column('session_no', sa.Integer(), nullable=False),
    sa.Column('starts_at', sa.DateTime(), nullable=True),
    sa.Column('ends_at', sa.DateTime(), nullable=True),
    sa.Column('meeting_url', sa.String(), nullable=True),
    sa.Column('location', sa.Text(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('status', postgresql.ENUM('scheduled', 'completed', 'cancelled', name='booking_session_status', create_type=False), server_default=sa.text("'scheduled'"), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('(starts_at IS NULL AND ends_at IS NULL) OR (starts_at IS NOT NULL AND ends_at IS NOT NULL AND ends_at > starts_at)', name=op.f('ck_booking_sessions_valid_session_interval')),
    sa.CheckConstraint('session_no > 0', name=op.f('ck_booking_sessions_positive_session_no')),
    sa.ForeignKeyConstraint(['booking_id'], ['booking.id'], name=op.f('fk_booking_sessions_booking_id_booking')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_booking_sessions')),
    sa.UniqueConstraint('booking_id', 'session_no', name=op.f('uq_booking_sessions_booking_id_session_no'))
    )
    op.create_index(op.f('ix_booking_sessions_starts_at'), 'booking_sessions', ['starts_at'], unique=False)
    op.create_table('booking_settlements',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('booking_id', sa.Uuid(), nullable=False),
    sa.Column('tutor_wallet_id', sa.Uuid(), nullable=False),
    sa.Column('total_amount', sa.BigInteger(), nullable=False),
    sa.Column('commission_rate', sa.Integer(), nullable=False),
    sa.Column('platform_fee', sa.BigInteger(), nullable=False),
    sa.Column('tutor_income', sa.BigInteger(), nullable=False),
    sa.Column('available_amount', sa.BigInteger(), nullable=False),
    sa.Column('hold_amount', sa.BigInteger(), nullable=False),
    sa.Column('status', postgresql.ENUM('held', 'released', 'refunded', name='escrow_status', create_type=False), server_default=sa.text("'held'"), nullable=False),
    sa.Column('release_date', sa.DateTime(), nullable=True),
    sa.Column('actual_released_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('commission_rate >= 0 AND commission_rate <= 100', name=op.f('ck_booking_settlements_commission_range')),
    sa.CheckConstraint('total_amount = platform_fee + tutor_income', name=op.f('ck_booking_settlements_total_allocation')),
    sa.CheckConstraint('total_amount >= 0 AND platform_fee >= 0 AND tutor_income >= 0 AND available_amount >= 0 AND hold_amount >= 0', name=op.f('ck_booking_settlements_nonnegative_amounts')),
    sa.CheckConstraint('tutor_income = available_amount + hold_amount', name=op.f('ck_booking_settlements_income_allocation')),
    sa.ForeignKeyConstraint(['booking_id'], ['booking.id'], name=op.f('fk_booking_settlements_booking_id_booking')),
    sa.ForeignKeyConstraint(['tutor_wallet_id'], ['wallets.id'], name=op.f('fk_booking_settlements_tutor_wallet_id_wallets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_booking_settlements')),
    sa.UniqueConstraint('booking_id', name=op.f('uq_booking_settlements_booking_id'))
    )
    op.create_index(op.f('ix_booking_settlements_release_date'), 'booking_settlements', ['release_date'], unique=False)
    op.create_index(op.f('ix_booking_settlements_tutor_wallet_id_status'), 'booking_settlements', ['tutor_wallet_id', 'status'], unique=False)
    op.create_table('comment_report',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('reporter_id', sa.Uuid(), nullable=True),
    sa.Column('target_id', sa.Uuid(), nullable=True),
    sa.Column('reason_category', sa.String(), nullable=True),
    sa.Column('reason_details', sa.Text(), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.Column('admin_id', sa.Uuid(), nullable=True),
    sa.Column('status', postgresql.ENUM('pending', 'approved', 'rejected', name='request_status', create_type=False), server_default=sa.text("'pending'"), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('locked_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['admin_id'], ['users.id'], name=op.f('fk_comment_report_admin_id_users')),
    sa.ForeignKeyConstraint(['reporter_id'], ['users.id'], name=op.f('fk_comment_report_reporter_id_users')),
    sa.ForeignKeyConstraint(['target_id'], ['comments.id'], name=op.f('fk_comment_report_target_id_comments')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_comment_report'))
    )
    op.create_table('disputes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('booking_id', sa.Uuid(), nullable=False),
    sa.Column('raised_by_user_id', sa.Uuid(), nullable=False),
    sa.Column('admin_id', sa.Uuid(), nullable=True),
    sa.Column('reason_category', sa.String(), nullable=True),
    sa.Column('is_completed', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('verdict', postgresql.ENUM('refund_full', 'refund_partial', 'rejected', name='dispute_verdict', create_type=False), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('resolve_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['admin_id'], ['users.id'], name=op.f('fk_disputes_admin_id_users')),
    sa.ForeignKeyConstraint(['booking_id'], ['booking.id'], name=op.f('fk_disputes_booking_id_booking')),
    sa.ForeignKeyConstraint(['raised_by_user_id'], ['users.id'], name=op.f('fk_disputes_raised_by_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_disputes')),
    sa.UniqueConstraint('booking_id', name=op.f('uq_disputes_booking_id')),
    sa.UniqueConstraint('id', 'booking_id', name=op.f('uq_disputes_id_booking_id'))
    )
    op.create_table('external_transaction',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('source_wallet_id', sa.Uuid(), nullable=True),
    sa.Column('destination_wallet_id', sa.Uuid(), nullable=True),
    sa.Column('amount', sa.Integer(), nullable=True),
    sa.Column('cash_order_id', sa.Uuid(), nullable=True),
    sa.Column('balance_before', sa.Integer(), nullable=True),
    sa.Column('balance_after', sa.Integer(), nullable=True),
    sa.Column('checksum', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('created_by_admin_id', sa.Uuid(), nullable=True),
    sa.Column('ref_log_id', sa.Uuid(), nullable=True),
    sa.ForeignKeyConstraint(['cash_order_id'], ['cash_order.id'], name=op.f('fk_external_transaction_cash_order_id_cash_order')),
    sa.ForeignKeyConstraint(['created_by_admin_id'], ['users.id'], name=op.f('fk_external_transaction_created_by_admin_id_users')),
    sa.ForeignKeyConstraint(['destination_wallet_id'], ['wallets.id'], name=op.f('fk_external_transaction_destination_wallet_id_wallets')),
    sa.ForeignKeyConstraint(['ref_log_id'], ['action_logs.id'], name=op.f('fk_external_transaction_ref_log_id_action_logs')),
    sa.ForeignKeyConstraint(['source_wallet_id'], ['wallets.id'], name=op.f('fk_external_transaction_source_wallet_id_wallets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_external_transaction'))
    )
    op.create_index(op.f('ix_external_transaction_cash_order_id'), 'external_transaction', ['cash_order_id'], unique=False)
    op.create_index(op.f('ix_external_transaction_created_at'), 'external_transaction', ['created_at'], unique=False)
    op.create_index(op.f('ix_external_transaction_destination_wallet_id'), 'external_transaction', ['destination_wallet_id'], unique=False)
    op.create_index(op.f('ix_external_transaction_source_wallet_id'), 'external_transaction', ['source_wallet_id'], unique=False)
    op.create_table('messages',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('booking_id', sa.Uuid(), nullable=False),
    sa.Column('dispute_id', sa.Uuid(), nullable=True),
    sa.Column('sender_id', sa.Uuid(), nullable=False),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('file_url', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('content IS NOT NULL OR file_url IS NOT NULL', name=op.f('ck_messages_content_or_file')),
    sa.ForeignKeyConstraint(['booking_id'], ['booking.id'], name=op.f('fk_messages_booking_id_booking')),
    sa.ForeignKeyConstraint(['dispute_id', 'booking_id'], ['disputes.id', 'disputes.booking_id'], name=op.f('fk_messages_dispute_id_booking_id_disputes')),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], name=op.f('fk_messages_sender_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_messages'))
    )
    op.create_index(op.f('ix_messages_booking_id_created_at'), 'messages', ['booking_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_messages_dispute_id_created_at'), 'messages', ['dispute_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('messages')
    op.drop_table('external_transaction')
    op.drop_table('disputes')
    op.drop_table('comment_report')
    op.drop_table('booking_settlements')
    op.drop_table('booking_sessions')
    op.drop_table('attendance')
    op.drop_table('wallet_snapshots')
    op.drop_table('internal_transaction')
    op.drop_table('course_progress')
    op.drop_table('comments')
    op.drop_table('cash_order')
    op.drop_table('booking')
    op.drop_table('wallets')
    op.drop_table('user_subscriptions')
    op.drop_table('role_requests')
    op.drop_table('posts')
    op.drop_table('payment_method')
    op.drop_table('lessons')
    op.drop_table('auth_sessions')
    op.drop_table('action_logs')
    op.drop_table('users')
    op.drop_table('tutoring_package')
    op.drop_table('credit_package')
    op.drop_table('courses')
    postgresql.ENUM('refund_full', 'refund_partial', 'rejected', name='dispute_verdict', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('held', 'released', 'refunded', name='escrow_status', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('scheduled', 'completed', 'cancelled', name='booking_session_status', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('recharge', 'payment', 'revenue', 'withdraw', 'refund', name='transaction_type', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('excellent', 'good', 'failed', name='course_result', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('pending', 'success', 'failed', name='cash_order_status', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('in', 'out', name='cash_order_type', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('pending', 'confirmed', 'assigned', 'completed', 'cancelled', 'refunded', 'disputing', name='booking_status', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('normal', 'commercial', name='wallet_type', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('active', 'expired', 'cancelled', name='subscription_status', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('booking', 'course', name='service_type', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('pending', 'approved', 'rejected', name='request_status', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('active', 'suspended', 'banned', name='user_status', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('guest', 'member', 'student', 'trainee_tutor', 'tutor', 'admin', 'head_admin', name='user_role', create_type=False).drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM('visible', 'hidden', name='course_status', create_type=False).drop(op.get_bind(), checkfirst=False)
