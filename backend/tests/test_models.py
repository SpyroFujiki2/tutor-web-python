import unittest
import warnings
from collections import Counter

from sqlalchemy import create_mock_engine
from sqlalchemy.exc import SAWarning
from sqlalchemy.orm import configure_mappers

from app.models import Base
from app.models.enums import CashOrderType, UserRole, cash_order_type_enum, user_role_enum


class ModelMappingTests(unittest.TestCase):
    def test_all_mappers_configure_without_warnings(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", SAWarning)
            configure_mappers()
        self.assertEqual(
            {mapper.local_table.name for mapper in Base.registry.mappers},
            set(Base.metadata.tables),
        )

    def test_complete_schema_compiles_for_postgresql_without_a_connection(self):
        statements = []

        def collect(sql, *args, **kwargs):
            statements.append(str(sql.compile(dialect=engine.dialect)).strip())

        engine = create_mock_engine("postgresql://", collect)
        Base.metadata.create_all(engine)
        created_tables = [sql for sql in statements if sql.startswith("CREATE TABLE")]
        self.assertEqual(len(created_tables), len(Base.metadata.tables))
        enum_names = [sql.split()[2] for sql in statements if sql.startswith("CREATE TYPE")]
        self.assertTrue(enum_names)
        self.assertTrue(all(count == 1 for count in Counter(enum_names).values()))
        # Shared enum objects must also drop cleanly in reverse dependency order.
        Base.metadata.drop_all(engine)
        dropped_tables = [sql for sql in statements if sql.startswith("DROP TABLE")]
        self.assertEqual(len(dropped_tables), len(Base.metadata.tables))

    def test_enum_values_are_persisted_instead_of_python_member_names(self):
        dialect = create_mock_engine("postgresql://", lambda *args, **kwargs: None).dialect
        for enum_type, member, value in (
            (cash_order_type_enum, CashOrderType.IN, "in"),
            (user_role_enum, UserRole.HEAD_ADMIN, "head_admin"),
        ):
            with self.subTest(enum=enum_type.name):
                self.assertEqual(enum_type.bind_processor(dialect)(member), value)
                self.assertIs(enum_type.result_processor(dialect, None)(value), member)


if __name__ == "__main__":
    unittest.main()
