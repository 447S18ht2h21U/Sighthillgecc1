import copy
import json
import time
from io import StringIO
from unittest.mock import patch
from django.core.management import call_command
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from . import tests as foundation
from .models import AuditEvent, Role, User
from .services import audit, transition


@override_settings(DEBUG=True)
class AuditCoverageTests(TestCase):
    setUp = foundation.FoundationTests.setUp

    def last(self, action):
        return AuditEvent.objects.filter(action=action).latest('sequence')

    def test_login_failure_does_not_attribute_unverified_identity_or_leak_input(self):
        secret = 'NeverRetainThisPassword!123'
        for data in [{'username': 'sales', 'password': secret},
                     {'username': 'unknown-private@example.invalid', 'password': secret},
                     {'username': ['sales'], 'password': secret}]:
            self.assertEqual(self.client.post('/api/dev-login/', data, format='json').status_code, 400)
            event = self.last('auth.login_failed')
            self.assertIsNone(event.actor_id)
            self.assertIsNone(event.payload['_context']['actor_role'])
            self.assertNotIn(secret, json.dumps(event.payload))
            self.assertNotIn('unknown-private', json.dumps(event.payload))
        self.assertEqual(self.client.post('/api/dev-login/', '{bad', content_type='application/json').status_code, 400)
        call_command('verify_audit', stdout=StringIO())

    def test_login_logout_and_expiry_are_recorded_without_extending_idle_clock(self):
        self.assertEqual(self.client.post('/api/dev-login/', {'username': 'sales', 'password': 'LocalPassword123!'}, format='json').status_code, 200)
        event = self.last('auth.login_succeeded')
        self.assertEqual(event.actor_id, self.sales.id)
        self.assertEqual(event.payload['_context']['actor_role'], Role.SALES_ASSOCIATE)
        session = self.client.session
        last = time.time() - 100
        session['last_activity'] = last; session.save()
        self.assertEqual(self.client.get('/api/projects/').status_code, 200)
        self.assertEqual(self.client.session['last_activity'], last)
        self.assertEqual(self.client.post('/api/logout/').status_code, 200)
        self.assertEqual(self.last('auth.logout').actor_id, self.sales.id)
        self.client.force_login(self.sales)
        session = self.client.session; session['last_activity'] = time.time() - 1801; session.save()
        self.assertEqual(self.client.get('/api/projects/').status_code, 403)
        self.assertEqual(self.last('auth.session_expired').actor_id, self.sales.id)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_denied_scoped_read_and_mutation_are_audited_after_rollback(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/projects/{self.project.id}/?secret=never-store').status_code, 404)
        event = self.last('access.unavailable')
        self.assertEqual(event.entity_id, self.project.id)
        self.assertNotIn('never-store', json.dumps(event.payload))
        self.client.force_authenticate(self.sales)
        record = self.edit_submit()
        count = AuditEvent.objects.filter(action='msr.approve').count()
        self.assertEqual(self.client.post(f'/api/msrs/{record.id}/transition/', {'action': 'approve', 'expected_sequence': record.edit_sequence}, format='json').status_code, 403)
        self.assertEqual(AuditEvent.objects.filter(action='msr.approve').count(), count)
        self.assertEqual(self.last('access.denied').entity_id, record.id)
        record.refresh_from_db(); self.assertEqual(record.status, 'SUBMITTED')

    edit_submit = foundation.FoundationTests.edit_submit
    approve = foundation.FoundationTests.approve

    def test_csrf_denial_is_recorded_with_no_request_body(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(client.post('/api/dev-login/', {'username': 'sales', 'password': 'SensitivePassword!123'}, format='json').status_code, 403)
        event = self.last('access.denied')
        self.assertIsNone(event.actor_id)
        self.assertNotIn('SensitivePassword', json.dumps(event.payload))

    def test_reads_downloads_and_audit_search_are_recorded_once(self):
        self.client.force_authenticate(self.comptroller)
        for path in ['/api/customers/', '/api/contacts/', '/api/projects/', '/api/accounts/', '/api/directory/', '/api/audit/?search=PrivateSearchValue']:
            before = AuditEvent.objects.filter(action='access.read').count()
            self.assertEqual(self.client.get(path).status_code, 200)
            self.assertEqual(AuditEvent.objects.filter(action='access.read').count(), before + 1)
        event = self.last('access.read')
        self.assertEqual(event.payload['_context']['route'], 'audit-list')
        self.assertNotIn('PrivateSearchValue', json.dumps(event.payload))
        record = self.approve()
        from .documents import generate
        doc, _ = generate(self.manager, record.id, 'CONTRACT')
        self.assertEqual(self.client.get(f'/api/documents/{doc.id}/download/').status_code, 200)
        self.assertEqual(self.last('access.download').entity_id, doc.id)

    def test_audit_history_snapshot_does_not_shift_under_its_own_reads(self):
        self.client.force_authenticate(self.comptroller)
        for n in range(55): audit(self.sales, 'customer.synthetic', self.customer.id, {'note': str(n)})
        first = self.client.get('/api/audit/').data
        audit(self.sales, 'customer.synthetic', self.customer.id, {'note': 'Newer event'})
        second = self.client.get(first['next']).data
        self.assertEqual(first['count'], second['count'])
        self.assertEqual(first['snapshot_sequence'], second['snapshot_sequence'])
        self.assertEqual(set(r['id'] for r in first['results']) & set(r['id'] for r in second['results']), set())
        self.assertEqual(len(first['results']) + len(second['results']), first['count'])
        self.assertGreater(self.client.get('/api/audit/').data['count'], first['count'])
        self.assertEqual(self.client.get('/api/audit/?through_sequence=-1').status_code, 400)
        self.assertEqual(self.client.get('/api/audit/?through_sequence=99999999999').status_code, 400)

    def test_role_source_context_and_draft_before_after_are_immutable(self):
        original = audit(self.sales, 'customer.synthetic', self.customer.id, {})
        User.objects.filter(pk=self.sales.id).update(role=Role.COMPTROLLER)
        newer = audit(self.sales, 'customer.synthetic', self.customer.id, {})
        original.refresh_from_db()
        self.assertEqual(original.payload['_context']['actor_role'], Role.SALES_ASSOCIATE)
        self.assertEqual(newer.payload['_context']['actor_role'], Role.COMPTROLLER)
        self.assertEqual(original.payload['_context']['source'], 'APPLICATION')
        before = copy.deepcopy(self.project.pending.snapshot)
        transition(self.manager, self.project.pending.id, 'edit', 0, snapshot=self.snapshot)
        edit = self.last('msr.edit')
        self.assertEqual(edit.payload['before'], before)
        self.assertEqual(edit.payload['after'], self.snapshot)
        with self.assertRaises(DatabaseError), transaction.atomic():
            AuditEvent.objects.filter(pk=original.id).update(payload={})
        with self.assertRaises(DatabaseError), transaction.atomic():
            AuditEvent.objects.filter(pk=original.id).delete()
        call_command('verify_audit', stdout=StringIO())

    def test_audit_unavailability_blocks_read_and_login(self):
        self.client.force_authenticate(self.comptroller)
        with patch('core.audit_middleware.audit', side_effect=RuntimeError('Unavailable')):
            response = self.client.get('/api/customers/')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(self.customer.legal_name, response.content.decode())
        self.client.force_authenticate(None)
        with patch('core.api.audit', side_effect=RuntimeError('Unavailable')), self.assertRaises(RuntimeError):
            self.client.post('/api/dev-login/', {'username': 'sales', 'password': 'LocalPassword123!'}, format='json')
        self.assertNotIn('_auth_user_id', self.client.session)
