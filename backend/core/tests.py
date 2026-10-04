import copy
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from django.test import TestCase, override_settings
from django.db import DatabaseError, connection, transaction
from django.core.management import call_command
from rest_framework.test import APIClient
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import User, Role, Customer, MSR, AuditEvent, Outbox, Project
from .services import create_project, transition, revise, validate_snapshot, change_project_state
from .rules import installation_eligible_at

@override_settings(DEBUG=True)
class FoundationTests(TestCase):
    def setUp(self):
        self.sales = User.objects.create_user(username='sales', role=Role.SALES_ASSOCIATE, initials='HS', password='LocalPassword123!')
        self.manager = User.objects.create_user(username='manager', role=Role.SALES_MANAGER, initials='SM', password='LocalPassword123!')
        self.comptroller = User.objects.create_user(username='comptroller', role=Role.COMPTROLLER, initials='CP', password='LocalPassword123!')
        self.other = User.objects.create_user(username='other', role=Role.SALES_ASSOCIATE, initials='OT', password='LocalPassword123!')
        self.customer = Customer.objects.create(legal_name='Example Customer', billing_address='10 Main Street', created_by=self.sales)
        self.project = create_project(self.sales, self.customer, '12 Main Street', self.sales, self.manager)
        self.snapshot = copy.deepcopy(self.project.pending.snapshot)
        self.snapshot.update(scope='Install heat pump', equipment=[{'description':'Heat pump', 'quantity':'1'}], materials=[], base_price='10000.00', total_price='10000.00', payment_terms='50% deposit when legally eligible; balance upon completion.')
        self.client = APIClient()
    def edit_submit(self):
        item = transition(self.sales, self.project.pending.id, 'edit', 0, snapshot=self.snapshot)
        return transition(self.sales, item.id, 'submit', item.edit_sequence)
    def approve(self):
        item = self.edit_submit()
        return transition(self.manager, item.id, 'approve', item.edit_sequence)
    def test_project_code_and_uuid(self):
        self.assertRegex(self.project.code, r'^\d+-HS-\d{4}-\d{2}-\d{2}$')
        self.assertEqual(self.project.pending.number, 1)
    def test_incomplete_submission_fails_atomically(self):
        before = AuditEvent.objects.count()
        with self.assertRaises(ValidationError):
            transition(self.sales, self.project.pending.id, 'submit', 0)
        self.project.pending.refresh_from_db()
        self.assertEqual(self.project.pending.status, 'DRAFT')
        self.assertEqual(AuditEvent.objects.count(), before)
    def test_sales_associate_cannot_approve(self):
        item = self.edit_submit()
        with self.assertRaises(PermissionDenied):
            transition(self.sales, item.id, 'approve', item.edit_sequence)
    def test_submitted_freezes_fields(self):
        item = self.edit_submit()
        with self.assertRaises(ValidationError):
            transition(self.sales, item.id, 'edit', item.edit_sequence, snapshot=self.snapshot)
        with self.assertRaises(DatabaseError), transaction.atomic():
            MSR.objects.filter(pk=item.pk).update(snapshot={'tampered':True})
    def test_approved_database_immutability(self):
        item = self.approve()
        for changes in [{'snapshot':{'tampered':True}}, {'status':'DRAFT'}, {'revision_reason':'tamper'}]:
            with self.assertRaises(DatabaseError), transaction.atomic():
                MSR.objects.filter(pk=item.pk).update(**changes)
        with self.assertRaises(DatabaseError), transaction.atomic():
            MSR.objects.filter(pk=item.pk).delete()
    def test_revision_preserves_current_approved(self):
        approved = self.approve()
        draft = revise(self.sales, self.project.id, 'Change scope', str(approved.id))
        self.project.refresh_from_db()
        self.assertEqual(draft.number, 2)
        self.assertEqual(draft.source_id, approved.id)
        self.assertEqual(self.project.current_approved_id, approved.id)
        item = transition(self.sales, draft.id, 'submit', 0)
        transition(self.comptroller, item.id, 'approve', item.edit_sequence)
        self.project.refresh_from_db()
        self.assertEqual(self.project.current_approved_id, draft.id)
        self.assertIsNone(self.project.pending_id)
    def test_rejection_history_retains_snapshot(self):
        item = self.edit_submit()
        item = transition(self.manager, item.id, 'reject', item.edit_sequence, reason='Clarify scope')
        updated = {**self.snapshot, 'scope':'Install replacement heat pump'}
        transition(self.sales, item.id, 'edit', item.edit_sequence, snapshot=updated)
        event = AuditEvent.objects.get(action='msr.reject')
        self.assertEqual(event.payload['snapshot']['scope'], 'Install heat pump')
        self.assertEqual(event.payload['reason'], 'Clarify scope')
    def test_self_review_blocked_after_manager_edits(self):
        item = transition(self.manager, self.project.pending.id, 'edit', 0, snapshot=self.snapshot)
        item = transition(self.manager, item.id, 'submit', item.edit_sequence)
        with self.assertRaises(PermissionDenied):
            transition(self.manager, item.id, 'approve', item.edit_sequence)
        transition(self.comptroller, item.id, 'approve', item.edit_sequence)
    def test_stale_edits_cannot_overwrite(self):
        transition(self.sales, self.project.pending.id, 'edit', 0, snapshot=self.snapshot)
        with self.assertRaises(ValidationError):
            transition(self.sales, self.project.pending.id, 'edit', 0, snapshot=self.snapshot)
    def test_duplicate_project_requires_reason(self):
        with self.assertRaises(ValidationError):
            create_project(self.sales, self.customer, '12 Main Street', self.sales, self.manager)
        create_project(self.sales, self.customer, '12 Main Street', self.sales, self.manager, 'Separate upstairs unit')
        self.assertEqual(Project.objects.count(), 2)
    def test_other_sales_associate_cannot_view_project_or_customer(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/projects/{self.project.id}/').status_code, 404)
        self.assertEqual(self.client.get('/api/customers/').json()['results'], [])
    def test_inactive_business_roles_no_commercial_access(self):
        for role in [Role.TECHNICIAN, Role.ACCOUNTS_PAYABLE_ASSOCIATE, Role.DATABASE_ADMINISTRATOR, Role.INSTALLATION_MANAGER]:
            self.other.role = role
            self.other.save()
            self.client.force_authenticate(self.other)
            self.assertEqual(self.client.get('/api/projects/').json()['results'], [])
            self.assertEqual(self.client.get('/api/audit/').status_code, 403)
    def test_account_management_comptroller_only(self):
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.get('/api/accounts/').status_code, 403)
        self.client.force_authenticate(self.comptroller)
        self.assertEqual(self.client.get('/api/accounts/').status_code, 200)
        response = self.client.post('/api/accounts/', {'username':'new', 'email':'new@example.com', 'role':Role.SALES_ASSOCIATE, 'initials':'NW', 'password':'short'}, format='json')
        self.assertEqual(response.status_code, 400)
    def test_customer_edits_never_modify_approved_snapshot(self):
        approved = self.approve()
        self.client.force_authenticate(self.sales)
        self.assertEqual(self.client.patch(f'/api/customers/{self.customer.id}/', {'legal_name':'Changed Name'}, format='json').status_code, 200)
        approved.refresh_from_db()
        self.assertEqual(approved.snapshot['customer'], 'Example Customer')
    def test_audit_chain_and_outbox_atomicity(self):
        self.approve()
        self.assertEqual(AuditEvent.objects.count(), Outbox.objects.count())
        call_command('verify_audit')
        with self.assertRaises(DatabaseError), transaction.atomic():
            AuditEvent.objects.all().update(action='tampered')
    def test_polling_does_not_extend_idle_session(self):
        self.client.force_authenticate(user=None)
        self.client.login(username='sales', password='LocalPassword123!')
        session = self.client.session
        value = time.time() - 100
        session['last_activity'] = value
        session.save()
        self.assertEqual(self.client.get('/api/me/').status_code, 200)
        self.assertEqual(self.client.session['last_activity'], value)
        session = self.client.session
        session['last_activity'] = time.time() - 1801
        session.save()
        self.assertEqual(self.client.get('/api/me/').status_code, 403)
    def test_activity_extends_valid_session(self):
        self.client.login(username='sales', password='LocalPassword123!')
        session = self.client.session
        session['last_activity'] = time.time() - 100
        session.save()
        self.assertEqual(self.client.post('/api/activity/', {}, format='json').status_code, 200)
        self.assertLess(time.time() - self.client.session['last_activity'], 5)
    def test_csrf_required_for_login(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(client.post('/api/dev-login/', {'username':'sales','password':'LocalPassword123!'}, format='json').status_code, 403)
        token = client.get('/api/csrf/').json()['csrfToken']
        self.assertEqual(client.post('/api/dev-login/', {'username':'sales','password':'LocalPassword123!'}, format='json', HTTP_X_CSRFTOKEN=token).status_code, 200)
    def test_money_validation_and_payment_options(self):
        for option in ['50_PERCENT_DEPOSIT', '100_PERCENT_COMPLETION']:
            validate_snapshot({**self.snapshot, 'payment_option':option}, complete=True)
        for value in ['NaN', '-1', '1.234']:
            with self.assertRaises(ValidationError):
                validate_snapshot({**self.snapshot, 'total_price':value}, complete=True)
        with self.assertRaises(ValidationError):
            validate_snapshot({**self.snapshot, 'total_price':'99.00'}, complete=True)
    def test_five_calendar_days_across_dst_and_rescission(self):
        eastern = ZoneInfo('America/New_York')
        signed = datetime(2026, 3, 6, 10, tzinfo=eastern)
        deadline = datetime(2026, 3, 7, 10, tzinfo=eastern)
        gate = installation_eligible_at(signed, signed, deadline)
        self.assertEqual(gate, datetime(2026, 3, 11, 10, tzinfo=eastern))
        self.assertEqual((gate.timestamp() - signed.timestamp()) / 3600, 119)
        later = datetime(2026, 3, 15, 10, tzinfo=eastern)
        self.assertEqual(installation_eligible_at(signed, signed, later), later)
        self.assertIsNone(installation_eligible_at(signed, None, deadline))
    def test_api_full_lifecycle(self):
        self.client.force_authenticate(self.sales)
        response = self.client.post(f'/api/msrs/{self.project.pending.id}/transition/', {'action':'edit','expected_sequence':0,'snapshot':self.snapshot}, format='json')
        self.assertEqual(response.status_code, 200)
        response = self.client.post(f'/api/msrs/{self.project.pending.id}/transition/', {'action':'submit','expected_sequence':1}, format='json')
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(self.manager)
        response = self.client.post(f'/api/msrs/{self.project.pending.id}/transition/', {'action':'approve','expected_sequence':2}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(f'/api/projects/{self.project.id}/').json()['current_approved']['number'], 1)
    def test_project_sequence_not_reused_after_rollback_postgres(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL sequence behavior only')
        with connection.cursor() as cursor:
            cursor.execute("SELECT nextval('gecc_project_number')")
            before = cursor.fetchone()[0]
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT nextval('gecc_project_number')")
                raise ValueError('rollback')
        except ValueError:
            pass
        with connection.cursor() as cursor:
            cursor.execute("SELECT nextval('gecc_project_number')")
            self.assertEqual(cursor.fetchone()[0], before + 2)

    def test_cancel_and_reopen_preserve_code_and_approval(self):
        approved = self.approve()
        code = self.project.code
        change_project_state(self.manager, self.project.id, 'cancel', 'Customer requested cancellation', 'APPROVED')
        self.project.refresh_from_db()
        self.assertEqual(self.project.state, 'CANCELLED')
        with self.assertRaises(ValidationError):
            revise(self.sales, self.project.id, 'Change scope', str(approved.id))
        change_project_state(self.comptroller, self.project.id, 'reopen', 'Customer authorized restart', 'CANCELLED')
        self.project.refresh_from_db()
        self.assertEqual(self.project.code, code)
        self.assertEqual(self.project.current_approved_id, approved.id)

    def test_api_customer_and_project_creation(self):
        self.client.force_authenticate(self.sales)
        customer = self.client.post('/api/customers/', {'legal_name':'Another Customer','billing_address':'20 New Street'}, format='json')
        self.assertEqual(customer.status_code, 201)
        response = self.client.post('/api/projects/', {'customer':customer.json()['id'],'location':'21 New Street','sales_associate':str(self.sales.id),'reviewer':str(self.manager.id)}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['pending']['number'], 1)
        self.assertIsNone(response.json()['current_approved'])
        self.assertEqual(response.json()['pending']['snapshot']['payment_option'], '50_PERCENT_DEPOSIT')

from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from django.test import TransactionTestCase
from django.db import close_old_connections, connections
from .models import AuditHead, LocalCounter

@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL concurrency checks')
@override_settings(DEBUG=True)
class PostgreSQLConcurrencyTests(TransactionTestCase):
    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)
        LocalCounter.objects.get_or_create(pk=1)
        self.sales = User.objects.create_user(username='sales', role=Role.SALES_ASSOCIATE, initials='SA')
        self.manager = User.objects.create_user(username='manager', role=Role.SALES_MANAGER, initials='SM')
        self.customer = Customer.objects.create(legal_name='Concurrent Customer', billing_address='1 Test Street', created_by=self.sales)
        self.project = create_project(self.sales, self.customer, '1 Test Street', self.sales, self.manager)
    def test_concurrent_edits_have_one_winner(self):
        user_id, record_id = self.sales.id, self.project.pending.id
        snapshot = copy.deepcopy(self.project.pending.snapshot)
        def edit(label):
            close_old_connections()
            try:
                transition(User.objects.get(pk=user_id), record_id, 'edit', 0, snapshot={**snapshot, 'scope':label})
                return 'saved'
            except ValidationError:
                return 'conflict'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(edit, ['Scope A','Scope B']))
        self.assertCountEqual(results, ['saved','conflict'])
        self.assertEqual(MSR.objects.get(pk=record_id).edit_sequence, 1)
        call_command('verify_audit')
    def test_concurrent_projects_have_unique_codes_and_audit_events(self):
        associate_id, reviewer_id, customer_id = self.sales.id, self.manager.id, self.customer.id
        def create(location):
            close_old_connections()
            try:
                project = create_project(User.objects.get(pk=associate_id), Customer.objects.get(pk=customer_id), location, User.objects.get(pk=associate_id), User.objects.get(pk=reviewer_id))
                return project.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            codes = list(executor.map(create, ['2 Test Street','3 Test Street']))
        self.assertEqual(len(set(codes)), 2)
        self.assertEqual(AuditEvent.objects.count(), 3)
        self.assertEqual(Outbox.objects.count(), 3)
        call_command('verify_audit')
