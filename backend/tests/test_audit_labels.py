import ast
from pathlib import Path
import unittest

from app.modules.users.audit_labels import (
    ACTION_LABELS, TARGET_LABELS, action_label, matching_codes, reason_label, target_label,
    ACTION_OPERATIONS, OPERATION_LABELS, operation_for,
)


class AuditLabelTests(unittest.TestCase):
    def test_rest_classification_covers_all_actions_and_preserves_ambiguous_history(self):
        self.assertEqual(ACTION_LABELS.keys(), ACTION_OPERATIONS.keys())
        self.assertEqual(operation_for('wallet.open'), 'POST')
        self.assertEqual(operation_for('cash.view_bank_details'), 'GET')
        self.assertEqual(operation_for('user.status'), 'PATCH')
        self.assertEqual(operation_for('lesson.remove'), 'DELETE')
        self.assertEqual(operation_for('course.save'), 'OTHER')
        self.assertEqual(operation_for('course.save', 'PUT'), 'PUT')
        self.assertEqual(operation_for('course.save', 'PATCH'), 'PATCH')
        self.assertEqual(operation_for('course.save', 'POST'), 'POST')
        self.assertEqual(operation_for('course.save', 'UPDATE'), 'PUT')
        self.assertEqual(operation_for('course.refund', 'UPDATE'), 'PATCH')
        self.assertEqual(operation_for('future.action'), 'OTHER')
        self.assertEqual(OPERATION_LABELS['OTHER'], 'Khác')
        self.assertEqual(OPERATION_LABELS['GET'], 'Xem (GET)')
        self.assertEqual(OPERATION_LABELS['POST'], 'Tạo mới (POST)')
        self.assertTrue(set(ACTION_OPERATIONS.values()) <= OPERATION_LABELS.keys())

    def test_every_persisted_action_has_a_vietnamese_label(self):
        backend = Path(__file__).resolve().parents[1]
        codes = {'vnpay.ipn', 'vnpay.querydr'}
        for directory in ('app', 'scripts'):
            for path in (backend / directory).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
                    if not isinstance(node, ast.Call):
                        continue
                    if isinstance(node.func, ast.Name) and node.func.id == 'audit' and len(node.args) >= 4:
                        value = node.args[3]
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            codes.add(value.value)
                    for keyword in node.keywords:
                        if keyword.arg == 'action_code' and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                            codes.add(keyword.value.value)
        self.assertFalse(codes - ACTION_LABELS.keys(), f'Missing labels: {codes - ACTION_LABELS.keys()}')

    def test_vietnamese_search_accepts_accents_case_and_unaccented_input(self):
        self.assertIn('wallet.open', matching_codes(ACTION_LABELS, '  MỞ VÍ  '))
        self.assertIn('wallet.open', matching_codes(ACTION_LABELS, 'mo vi'))
        self.assertIn('lesson.reorder', matching_codes(ACTION_LABELS, 'sap xep thu tu bai hoc'))
        self.assertIn('users', matching_codes(TARGET_LABELS, 'nguoi dung'))
        self.assertEqual(matching_codes(ACTION_LABELS, '%'), [])

    def test_automatic_reasons_are_translated_and_free_text_is_preserved(self):
        self.assertEqual(reason_label('Wallet opened with zero balances'), 'Mở ví với số dư ban đầu bằng 0')
        self.assertEqual(reason_label('Reviewed with customer'), 'Reviewed with customer')
        self.assertEqual(action_label('wallet.open'), 'Mở ví')
        self.assertEqual(action_label('future.action'), 'Thao tác khác')
        self.assertEqual(target_label('wallets'), 'Ví')


if __name__ == '__main__':
    unittest.main()
