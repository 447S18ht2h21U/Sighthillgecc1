import json
from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import User, Role, AuditEvent


@override_settings(DEBUG=True)
class AccountManagementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='controller', role=Role.COMPTROLLER, initials='CP', email='owner@example.invalid', password='TestingAccount2026!')
        self.target = User.objects.create_user(username='associate', role=Role.SALES_ASSOCIATE, initials='SA', email='sales@example.invalid', password='TestingAccount2026!')
        self.client = APIClient(); self.client.force_authenticate(self.owner)
        self.url = f'/api/accounts/{self.target.id}/'
        self.new = dict(username='newuser', first_name='Synthetic', last_name='User', email='new@example.invalid', initials='NU', role=Role.SALES_ASSOCIATE, password='SyntheticAccount2026!', is_active=True, change_note='Fictional local account test.')

    def change(self, **fields):
        revision = self.client.get(self.url).data['revision']
        return self.client.patch(self.url, {'expected_revision': revision, 'change_note':'Synthetic account update.', **fields}, format='json')

    def test_only_active_comptroller_can_list_create_or_change_accounts(self):
        for role in Role.values:
            if role == Role.COMPTROLLER: continue
            self.target.role=role;self.target.save();self.client.force_authenticate(self.target)
            for method, url, data in [('get','/api/accounts/',None),('post','/api/accounts/',self.new),('patch',f'/api/accounts/{self.owner.id}/',{'is_active':False})]:
                with self.subTest(role=role, method=method):self.assertEqual(getattr(self.client,method)(url,data,format='json').status_code,403)
        self.owner.is_active=False;self.owner.save();self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get('/api/accounts/').status_code,403)

    def test_creation_audits_safe_values_and_never_returns_credentials(self):
        response=self.client.post('/api/accounts/',self.new,format='json');self.assertEqual(response.status_code,201)
        user=User.objects.get(pk=response.data['id']);self.assertTrue(user.check_password(self.new['password']))
        event=AuditEvent.objects.get(action='account.created');self.assertEqual(event.payload['note'],self.new['change_note'])
        self.assertEqual(event.payload['after']['email'],self.new['email'])
        text=json.dumps({'response':response.data,'audit':event.payload})
        self.assertNotIn(self.new['password'],text);self.assertNotIn(user.password,text);self.assertNotIn('password',response.data)

    def test_role_and_deactivation_changes_are_audited_and_block_login(self):
        response=self.change(role=Role.TECHNICIAN,is_active=False);self.assertEqual(response.status_code,200)
        self.target.refresh_from_db();self.assertFalse(self.target.is_active)
        event=AuditEvent.objects.get(action='account.updated')
        self.assertEqual(event.payload['before']['role'],Role.SALES_ASSOCIATE)
        self.assertEqual(event.payload['after']['role'],Role.TECHNICIAN)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post('/api/dev-login/',{'username':'associate','password':'TestingAccount2026!'},format='json').status_code,400)

    def test_stale_or_missing_revision_cannot_overwrite_current_account(self):
        old=self.client.get(self.url).data['revision'];self.assertEqual(self.change(first_name='Latest').status_code,200)
        for revision in [old,None]:
            data={'first_name':'Stale','change_note':'Attempted stale update.'}
            if revision:data['expected_revision']=revision
            self.assertEqual(self.client.patch(self.url,data,format='json').status_code,400)
        self.target.refresh_from_db();self.assertEqual(self.target.first_name,'Latest')
        self.assertEqual(AuditEvent.objects.filter(action='account.updated').count(),1)

    def test_self_role_and_deactivation_are_blocked_but_profile_edit_allowed(self):
        url=f'/api/accounts/{self.owner.id}/';rev=self.client.get(url).data['revision']
        for fields in [{'role':Role.SALES_ASSOCIATE},{'is_active':False}]:
            self.assertEqual(self.client.patch(url,{'expected_revision':rev,'change_note':'Test self lockout guard.',**fields},format='json').status_code,400)
        self.assertEqual(self.client.patch(url,{'expected_revision':rev,'change_note':'Update my display name.','first_name':'Updated'},format='json').status_code,200)

    def test_notes_passwords_initials_and_roles_are_validated(self):
        for values in [{'change_note':''},{'password':'short'},{'initials':'lower'},{'role':'SYSTEM_ADMINISTRATOR'}]:
            self.assertEqual(self.client.post('/api/accounts/',{**self.new,**values},format='json').status_code,400)
        self.assertEqual(self.client.post('/api/accounts/',self.new,format='json').status_code,201)
        self.assertEqual(self.client.post('/api/accounts/',self.new,format='json').status_code,400)

    def test_password_reset_changes_revision_and_keeps_password_out_of_audit(self):
        old=self.client.get(self.url).data['revision'];password='NewSyntheticPassword2026!'
        response=self.change(password=password);self.assertEqual(response.status_code,200)
        self.assertNotEqual(old,response.data['revision']);self.target.refresh_from_db();self.assertTrue(self.target.check_password(password))
        event=AuditEvent.objects.get(action='account.updated');self.assertTrue(event.payload['password_changed'])
        self.assertNotIn(password,json.dumps(event.payload));self.assertNotIn(self.target.password,json.dumps(event.payload))

    def test_audit_failure_rolls_back_account_change(self):
        with patch('core.api.audit',side_effect=RuntimeError('synthetic audit failure')),self.assertRaises(RuntimeError):self.change(is_active=False)
        self.target.refresh_from_db();self.assertTrue(self.target.is_active)

    def test_deactivated_actor_is_rechecked_even_with_cached_authentication(self):
        self.owner.role=Role.SALES_MANAGER;self.owner.save()
        self.assertEqual(self.client.post('/api/accounts/',self.new,format='json').status_code,403)
        self.assertEqual(self.client.patch(self.url,{'change_note':'Stale Comptroller session.'},format='json').status_code,403)

    def test_session_mutations_require_csrf(self):
        client=APIClient(enforce_csrf_checks=True)
        token=client.get('/api/csrf/').json()['csrfToken']
        response=client.post('/api/dev-login/',{'username':'controller','password':'TestingAccount2026!'},format='json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,200)
        self.assertEqual(client.post('/api/accounts/',self.new,format='json').status_code,403)
        token=client.get('/api/csrf/').json()['csrfToken']
        self.assertEqual(client.post('/api/accounts/',self.new,format='json',HTTP_X_CSRFTOKEN=token).status_code,201)

    def test_account_lists_are_paginated_and_private(self):
        User.objects.bulk_create([User(username=f'page{i}',role=Role.TECHNICIAN,initials='PT') for i in range(51)])
        first=self.client.get('/api/accounts/');second=self.client.get('/api/accounts/?page=2')
        self.assertEqual(first.data['count'],53);self.assertEqual(len(first.data['results']),50)
        self.assertEqual(len(second.data['results']),3);self.assertIn('page=2',first.data['next'])
        self.assertEqual(first['Cache-Control'],'private, no-store')

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
    def test_production_provisioning_and_changes_stay_blocked(self):
        self.assertEqual(self.client.post('/api/accounts/',self.new,format='json').status_code,400)
        self.assertEqual(self.change(first_name='Blocked').status_code,400)
        self.target.refresh_from_db();self.assertEqual(self.target.first_name,'')
