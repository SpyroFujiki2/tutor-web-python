"""Opt-in migration cycles in a disposable loopback PostgreSQL schema."""

import os
import unittest
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.core.config import BACKEND_DIR, ROOT_DIR, get_database_settings
from app.core.database import expected_schema_heads
from app.models import Base, Course, CourseProgress, Lesson, User, UserSubscription
from app.models.enums import CourseStatus, ServiceType, SubscriptionStatus, UserRole, UserStatus
from app.modules.common import now
from app.modules.learning.learning_service import record_attendance


@unittest.skipUnless(os.environ.get('TUTOR_TEST_POSTGRES') == '1', 'Set TUTOR_TEST_POSTGRES=1 for isolated PostgreSQL tests')
class PostgreSQLMigrationTests(unittest.TestCase):
    def setUp(self):
        settings = get_database_settings()
        self.assertIn(settings.url.host, {'localhost', '127.0.0.1', '::1'})
        self.schema = 'tutor_migration_test_' + uuid4().hex
        self.control = create_engine(settings.url, hide_parameters=True)
        self.addCleanup(self.control.dispose)
        with self.control.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.addCleanup(self.drop_schema)
        self.engine = create_engine(settings.url, hide_parameters=True, connect_args={
            'options': f'-c search_path={self.schema} -c timezone=UTC -c statement_timeout=15000',
        })
        self.addCleanup(self.engine.dispose)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        self.config = Config(str(ROOT_DIR / 'alembic.ini'))
        self.config.set_main_option('script_location', str(BACKEND_DIR / 'migrations'))
        self.config.set_main_option('prepend_sys_path', str(BACKEND_DIR))

    def drop_schema(self):
        self.assertRegex(self.schema, r'^tutor_migration_test_[0-9a-f]{32}$')
        with self.control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))

    def migrate(self, target, *, downgrade=False):
        with patch('app.core.database.create_database_engine', return_value=self.engine):
            (command.downgrade if downgrade else command.upgrade)(self.config, target)

    def test_empty_database_upgrades_to_current_models_and_downgrades_cleanly(self):
        self.migrate('head')
        self.assertEqual(set(inspect(self.engine).get_table_names()), set(Base.metadata.tables) | {'alembic_version'})
        with self.engine.connect() as connection:
            self.assertEqual(frozenset(connection.scalars(text('SELECT version_num FROM alembic_version'))), expected_schema_heads())
            protected = connection.scalar(text(
                'SELECT count(*) FROM pg_class WHERE relnamespace = current_schema()::regnamespace '
                "AND relkind = 'r' AND relrowsecurity"))
            self.assertEqual(protected, len(Base.metadata.tables) + 1)
        self.migrate('base', downgrade=True)
        self.assertEqual(inspect(self.engine).get_table_names(), ['alembic_version'])

    def test_existing_watch_history_survives_upgrade_and_ungraded_completion_downgrade(self):
        self.migrate('0006_database_audit_operation')
        user_id, course_id, lesson_id, subscription_id = [uuid4() for _ in range(4)]
        with self.factory.begin() as session:
            session.add(User(id=user_id, role=UserRole.STUDENT, status=UserStatus.ACTIVE))
            session.add(Course(id=course_id, title='Migration fixture', price=0,
                               status=CourseStatus.VISIBLE, is_live=False, created_at=now(), updated_at=now()))
            session.flush()
            session.add(Lesson(id=lesson_id, course_id=course_id, order_idx=1, duration_seconds=600))
            session.add(UserSubscription(id=subscription_id, user_id=user_id, type=ServiceType.COURSE,
                title_at_purchase='Migration fixture', price_at_purchase=0,
                status=SubscriptionStatus.ACTIVE, activated_at=now()))
            session.flush()
            session.add(CourseProgress(subscription_id=subscription_id, course_id=course_id,
                                       progress_percent=Decimal('99.99')))
            session.flush()
            session.execute(text('INSERT INTO attendance (subscription_id, course_id, lesson_id, duration_watched, is_absent) '
                                 'VALUES (:subscription, :course, :lesson, 600, false)'),
                            {'subscription': subscription_id, 'course': course_id, 'lesson': lesson_id})
        self.migrate('head')
        with self.factory.begin() as session:
            progress = record_attendance(session, user_id, subscription_id, lesson_id, 600)
            self.assertEqual(progress.progress_percent, Decimal('100.00'))
            self.assertIsNotNone(progress.completed_at)
            self.assertIsNone(progress.final_score)
            self.assertIsNone(progress.result)
        self.migrate('0006_database_audit_operation', downgrade=True)
        with self.engine.connect() as connection:
            progress = connection.execute(text('SELECT progress_percent, completed_at FROM course_progress')).one()
            self.assertEqual(progress.progress_percent, Decimal('99.99'))
            self.assertIsNone(progress.completed_at)
            self.assertEqual(connection.scalar(text('SELECT duration_watched FROM attendance')), 600)
        self.migrate('head')
        with self.engine.connect() as connection:
            self.assertIs(connection.scalar(text('SELECT assignment_completed FROM attendance')), False)
