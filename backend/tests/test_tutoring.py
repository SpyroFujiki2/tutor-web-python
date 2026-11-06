from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.models import Message
from app.modules.tutoring.booking_session import session_action
from app.modules.tutoring.message import send_booking_message
from test_domain_api import DomainApiFixture


class TutoringTests(DomainApiFixture):
    def setUp(self):
        super().setUp()
        self.upload_root = Path(__file__).resolve().parents[1] / '.local' / 'tutoring-tests' / uuid4().hex
        self.upload_root.mkdir(parents=True)
        self.app.state.tutoring_upload_root = self.upload_root
        self.addCleanup(self.remove_uploads)

    def remove_uploads(self):
        expected = Path(__file__).resolve().parents[1] / '.local' / 'tutoring-tests'
        self.assertEqual(self.upload_root.parent, expected)
        for path in self.upload_root.iterdir():
            path.unlink()
        self.upload_root.rmdir()

    def upload(self, booking_id, *, who='customer', content=b'%PDF-1.7\nfixture', media_type='application/pdf', dispute_id=None, expected=201):
        query = '?name=fixture.pdf' + (f'&dispute_id={dispute_id}' if dispute_id else '')
        response = self.client.post(f'/api/bookings/{booking_id}/attachments' + query, content=content,
            headers={'Authorization': 'Bearer ' + self.tokens[who]['access_token'], 'Content-Type': media_type})
        self.assertEqual(response.status_code, expected, response.text)
        return response.json()

    def test_tutoring_package_commands_validate_role_and_deactivate_without_deleting_bookings(self):
        self.request('POST', '/admin/tutoring-packages', {'name': '  ', 'price': 100}, who='admin', expected=422)
        self.request('POST', '/admin/tutoring-packages', {'name': 'Denied', 'price': 100}, expected=403)
        booking = self.paid_booking()
        self.request('POST', f"/admin/tutoring-packages/{booking['package_id']}/deactivate", who='admin')
        self.assertEqual(self.request('GET', '/tutoring-packages'), [])
        self.assertEqual(self.request('GET', f"/bookings/{booking['id']}")['status'], 'confirmed')
        # Existing paid contracts retain their entitlement even after the package stops selling.
        self.request('POST', f"/admin/bookings/{booking['id']}/assign", {'tutor_id': str(self.ids['tutor'])}, who='admin')

    def test_changing_package_does_not_rewrite_paid_snapshot(self):
        booking = self.paid_booking()
        self.request('PUT', f"/admin/tutoring-packages/{booking['package_id']}", {'name': 'Updated', 'price': 900}, who='admin')
        subscriptions = self.request('GET', '/me/subscriptions')
        self.assertEqual(subscriptions[0]['price_at_purchase'], 100)
        self.assertEqual(subscriptions[0]['title_at_purchase'], 'Math')

    def test_direct_module_commands_enforce_closed_chat_and_known_session_actions(self):
        booking = self.create_booking()
        self.request('POST', f"/bookings/{booking['id']}/cancel")
        with self.factory.begin() as session:
            with self.assertRaises(ValueError):
                send_booking_message(session, booking_id=UUID(booking['id']), sender_id=self.ids['customer'], content='Closed')
            with self.assertRaises(ValueError):
                session_action(session, self.ids['customer'], UUID(booking['id']), uuid4(), 'unknown')

    def test_regular_attachments_require_participant_authorization_for_upload_and_download(self):
        booking = self.paid_booking()
        message = self.upload(booking['id'])
        self.assertTrue(message['file_url'].endswith('.pdf'))
        response = self.client.get(message['file_url'], headers={'Authorization': 'Bearer ' + self.tokens['customer']['access_token']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'%PDF-1.7\nfixture')
        self.assertIn('attachment', response.headers['content-disposition'])
        for who in ('other', 'admin'):
            self.assertEqual(self.client.get(message['file_url'], headers={'Authorization': 'Bearer ' + self.tokens[who]['access_token']}).status_code, 404)
        self.assertEqual(self.client.get(message['file_url']).status_code, 401)
        self.upload(booking['id'], who='other', expected=404)
        self.assertEqual(len(list(self.upload_root.iterdir())), 1)

    def test_dispute_attachment_is_separate_from_regular_chat_and_scoped_to_assignee(self):
        booking = self.paid_booking()
        dispute = self.request('POST', f"/bookings/{booking['id']}/dispute", {'reason_category': 'Evidence'})
        self.request('POST', f"/admin/disputes/{dispute['id']}/claim", who='admin')
        message = self.upload(booking['id'], who='admin', dispute_id=dispute['id'])
        self.assertEqual(self.request('GET', f"/bookings/{booking['id']}/messages"), [])
        self.assertEqual(len(self.request('GET', f"/bookings/{booking['id']}/messages?dispute_id={dispute['id']}")), 1)
        self.assertEqual(self.client.get(message['file_url'], headers={'Authorization': 'Bearer ' + self.tokens['head']['access_token']}).status_code, 404)
        self.assertEqual(self.client.get(message['file_url'], headers={'Authorization': 'Bearer ' + self.tokens['admin']['access_token']}).status_code, 200)

    def test_unsupported_mismatched_and_oversized_uploads_never_create_file_or_message(self):
        booking = self.paid_booking()
        self.upload(booking['id'], media_type='text/html', content=b'<script>bad</script>', expected=415)
        self.upload(booking['id'], content=b'not a pdf', expected=400)
        self.upload(booking['id'], content=b'x' * (5 * 1024 * 1024 + 1), expected=413)
        self.assertEqual(list(self.upload_root.iterdir()), [])
        self.assertEqual(self.request('GET', f"/bookings/{booking['id']}/messages"), [])

    def test_failed_commit_removes_uploaded_file_and_rolls_back_message(self):
        booking = self.paid_booking()
        def fail(_session):
            raise RuntimeError('Test commit failure')
        event.listen(self.factory, 'before_commit', fail)
        try:
            client = TestClient(self.app, raise_server_exceptions=False)
            self.addCleanup(client.close)
            response = client.post(f"/api/bookings/{booking['id']}/attachments?name=fixture.pdf", content=b'%PDF-1.7\nfixture',
                headers={'Authorization': 'Bearer ' + self.tokens['customer']['access_token'], 'Content-Type': 'application/pdf'})
        finally:
            event.remove(self.factory, 'before_commit', fail)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(list(self.upload_root.iterdir()), [])
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Message)), 0)

    def test_message_rate_limit_is_shared_by_files_and_text(self):
        booking = self.paid_booking()
        for index in range(30):
            self.request('POST', f"/bookings/{booking['id']}/messages", {'content': f'Message {index}'}, expected=201)
        self.request('POST', f"/bookings/{booking['id']}/messages", {'content': 'Limited'}, expected=429)
        self.upload(booking['id'], expected=429)
        self.assertEqual(list(self.upload_root.iterdir()), [])

    def test_dispute_rejection_restores_preexisting_booking_stage_and_blocks_reopening(self):
        booking = self.paid_booking()
        dispute = self.request('POST', f"/bookings/{booking['id']}/dispute", {'reason_category': 'Review'})
        self.request('POST', f"/admin/disputes/{dispute['id']}/claim", who='admin')
        self.request('POST', f"/admin/disputes/{dispute['id']}/decision", {'verdict': 'rejected', 'reason': 'Resolved'}, who='admin')
        self.assertEqual(self.request('GET', f"/bookings/{booking['id']}")['status'], 'confirmed')
        self.request('POST', f"/bookings/{booking['id']}/dispute", {'reason_category': 'Again'}, expected=400)

    def test_customer_cannot_schedule_or_complete_sessions_and_tutor_cannot_confirm_booking(self):
        booking = self.paid_booking()
        self.request('POST', f"/admin/bookings/{booking['id']}/assign", {'tutor_id': str(self.ids['tutor'])}, who='admin')
        session = self.request('GET', f"/bookings/{booking['id']}/sessions")[0]
        self.request('POST', f"/bookings/{booking['id']}/sessions/{session['id']}/action", {'action': 'complete'}, expected=403)
        self.request('POST', f"/bookings/{booking['id']}/complete", who='tutor', expected=403)
