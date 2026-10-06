import copy
import json
import os
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError
from . import docusign, reconciliation, sandbox
from .models import AuditEvent, Outbox, SandboxAttempt, SandboxObservation
from . import test_sandbox as fixtures
CONFIG = fixtures.CONFIG
from .signing import prepare


@override_settings(DEBUG=True)
class ReconciliationTests(TestCase):
    setUp = fixtures.SandboxTests.setUp
    edit_submit = fixtures.SandboxTests.edit_submit
    approve = fixtures.SandboxTests.approve
    setup_review = fixtures.SandboxTests.setup_review
    setup_package = fixtures.SandboxTests.setup_package
    start = fixtures.SandboxTests.start
    finish = fixtures.SandboxTests.finish
    provider_responses = fixtures.SandboxTests.provider_responses
    oauth_responses = fixtures.SandboxTests.oauth_responses

    def known_draft(self):
        self.setup_package()
        self.finish(self.start())
        self.attempt = SandboxAttempt.objects.get(package=self.package)

    def check_start(self, actor=None):
        with patch.dict(os.environ, CONFIG):
            result = reconciliation.begin(actor or self.comptroller, 'synthetic-session', self.package.id, True)
        return parse_qs(urlsplit(result['authorization_url']).query)['state'][0]

    def readings(self):
        p = self.provider_responses()
        p[1]['envelopeId'] = self.attempt.envelope_id
        return [p[1], p[2], p[3], copy.deepcopy(p[1])]

    def check_finish(self, state, readings=None, hook=None):
        with patch.dict(os.environ, CONFIG), patch('core.docusign.request_json', side_effect=self.oauth_responses()), patch('core.sandbox.provider', side_effect=hook or readings or self.readings()) as remote:
            result = docusign.finish(self.comptroller, 'synthetic-session', state, 'synthetic-code')
        return result, remote

    def test_matching_recheck_reads_only_and_preserves_creation_evidence(self):
        self.known_draft(); initial = copy.deepcopy(self.attempt.evidence)
        result, remote = self.check_finish(self.check_start())
        self.assertEqual(result['status'], 'SANDBOX_RECONCILIATION_MATCHED')
        self.assertEqual(remote.call_count, 4)
        for call in remote.call_args_list:
            self.assertNotIn('payload', call.kwargs)
            self.assertEqual(call.args[1], self.attempt.envelope_id)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, 'DRAFT_VALIDATED')
        self.assertEqual(self.attempt.evidence, initial)
        observation = SandboxObservation.objects.get()
        self.assertTrue(observation.evidence['metadata_matched'])
        self.assertFalse(observation.evidence['provider_pdf_bytes_verified'])
        self.assertFalse(sandbox.describe(self.package)['send_available'])
        stored = json.dumps(list(AuditEvent.objects.values('payload')))+json.dumps(observation.evidence)
        for secret in ['synthetic-access-token','synthetic-refresh-token','synthetic-client-secret','synthetic-code']:
            self.assertNotIn(secret, stored)

    def test_provider_changes_block_and_history_retains_prior_match(self):
        self.known_draft(); self.check_finish(self.check_start())
        for mutation in ['status', 'identity', 'routing', 'tabs', 'documents', 'extra', 'optional']:
            data = self.readings()
            if mutation == 'status': data[0]['status']=data[3]['status']='sent'
            elif mutation == 'identity': data[1]['signers'][0]['email']='other@example.invalid'
            elif mutation == 'routing': data[1]['signers'][0]['routingOrder']='2'
            elif mutation == 'tabs': data[1]['signers'][0]['tabs']['signHereTabs'][0]['xPosition']='999'
            elif mutation == 'documents': data[2]['envelopeDocuments'][0]['name']='replacement.pdf'
            elif mutation == 'extra': data[1]['carbonCopies']=[{'email':'extra@example.invalid'}]
            else: data[1]['signers'][0]['tabs']['signHereTabs'][0]['optional']='true'
            with self.subTest(mutation=mutation):
                result,_ = self.check_finish(self.check_start(), data)
                self.assertEqual(result['status'], 'SANDBOX_RECONCILIATION_CHANGED')
                self.attempt.refresh_from_db();self.assertEqual(self.attempt.state,'RECONCILIATION_REQUIRED')
        self.assertEqual(SandboxObservation.objects.count(), 8)
        self.assertTrue(SandboxObservation.objects.filter(evidence__outcome='MATCHED').exists())

    def test_failed_read_does_not_lose_envelope_or_retry_create(self):
        self.known_draft(); state=self.check_start()
        result,remote = self.check_finish(state, hook=TimeoutError('private-token-provider-body'))
        self.assertEqual(result['status'],'SANDBOX_RECONCILIATION_READ_FAILED')
        self.assertEqual(remote.call_count,1)
        self.attempt.refresh_from_db();self.assertEqual(self.attempt.state,'RECONCILIATION_REQUIRED')
        self.assertTrue(self.attempt.envelope_id)
        self.assertNotIn('private-token', json.dumps(SandboxObservation.objects.get().evidence))
        with patch.dict(os.environ,CONFIG),self.assertRaises(ValidationError):sandbox.begin_draft(self.comptroller,'session',self.package.id,True)
        result,_=self.check_finish(self.check_start());self.assertEqual(result['status'],'SANDBOX_RECONCILIATION_MATCHED')

    def test_envelope_changes_during_reads_block(self):
        self.known_draft();data=self.readings();data[3]['lastModifiedDateTime']='2026-10-06T12:00:00Z'
        result,_=self.check_finish(self.check_start(),data)
        self.assertEqual(result['status'],'SANDBOX_RECONCILIATION_CHANGED')

    def test_superseded_local_review_still_inspected_but_not_validated(self):
        self.known_draft()
        prepare(self.manager,self.approved.id,{**self.input,'customer_name':'Replacement Customer'})
        result,remote=self.check_finish(self.check_start())
        self.assertEqual(result['status'],'SANDBOX_RECONCILIATION_BLOCKED');self.assertEqual(remote.call_count,4)
        self.assertTrue(SandboxObservation.objects.get().evidence['metadata_matched'])
        self.attempt.refresh_from_db();self.assertEqual(self.attempt.state,'RECONCILIATION_REQUIRED')

    def test_local_change_during_network_cannot_restore_validation(self):
        self.known_draft();data=iter(self.readings());count=0
        def hook(*args,**kwargs):
            nonlocal count
            count+=1
            if count==4: prepare(self.manager,self.approved.id,{**self.input,'customer_name':'Replacement Customer'})
            return next(data)
        result,_=self.check_finish(self.check_start(),hook=hook)
        self.assertEqual(result['status'],'SANDBOX_RECONCILIATION_BLOCKED')

    def test_latest_authorization_wins_and_replay_never_reads(self):
        self.known_draft();old=self.check_start();new=self.check_start()
        with self.assertRaises(ValidationError):self.check_finish(old)
        self.assertFalse(SandboxObservation.objects.exists())
        self.check_finish(new)
        with self.assertRaises(ValidationError):self.check_finish(new)
        self.assertEqual(SandboxObservation.objects.count(),1)

    def test_new_check_during_reads_supersedes_older_result(self):
        self.known_draft();data=iter(self.readings());count=0
        def hook(*args,**kwargs):
            nonlocal count
            count+=1
            if count==4:self.check_start()
            return next(data)
        result,_=self.check_finish(self.check_start(),hook=hook)
        self.assertEqual(result['status'],'SANDBOX_RECONCILIATION_SUPERSEDED')
        self.attempt.refresh_from_db();self.assertEqual(self.attempt.state,'RECHECK_PENDING')

    def test_permissions_confirmation_account_and_production_gates(self):
        self.known_draft()
        with patch.dict(os.environ,CONFIG):
            with self.assertRaises(PermissionDenied):reconciliation.begin(self.manager,'session',self.package.id,True)
            with self.assertRaises(ValidationError):reconciliation.begin(self.comptroller,'session',self.package.id,'true')
            with self.assertRaises(ValidationError):reconciliation.begin(self.comptroller,'',self.package.id,True)
            with override_settings(DEBUG=False),self.assertRaises(ValidationError):self.check_start()
        with patch.dict(os.environ,{**CONFIG,'GECC_DOCUSIGN_ACCOUNT_ID':'44444444-4444-4444-8444-444444444444'}),self.assertRaises(ValidationError):
            reconciliation.begin(self.comptroller,'session',self.package.id,True)

    def test_unknown_envelope_and_inflight_create_cannot_be_checked(self):
        self.setup_package();self.start()
        with self.assertRaises(ValidationError):self.check_start()
        attempt=SandboxAttempt.objects.get(package=self.package);attempt.envelope_id='55555555-5555-4555-8555-555555555555';attempt.state='NETWORK_STARTED';attempt.save()
        with self.assertRaises(ValidationError):self.check_start()

    def test_immutable_observation_and_audit_atomic(self):
        self.known_draft();self.check_finish(self.check_start())
        observation=SandboxObservation.objects.get()
        with self.assertRaises(DatabaseError),transaction.atomic():SandboxObservation.objects.filter(pk=observation.id).update(evidence={})
        with self.assertRaises(DatabaseError),transaction.atomic():SandboxObservation.objects.filter(pk=observation.id).delete()
        state=self.check_start()
        with patch('core.reconciliation.audit',side_effect=RuntimeError('audit unavailable')),self.assertRaises(RuntimeError):self.check_finish(state)
        self.assertEqual(SandboxObservation.objects.count(),1)
        self.assertEqual(AuditEvent.objects.count(),Outbox.objects.count())
        self.attempt.refresh_from_db();self.assertEqual(self.attempt.state,'RECHECK_PENDING')

    def test_api_scoping_confirmation_session_and_parseable_history(self):
        self.known_draft();url=f'/api/sandbox-packages/{self.package.id}/connect-check/'
        self.client.force_authenticate(self.other);self.assertEqual(self.client.post(url,{},format='json').status_code,404)
        self.client.force_authenticate(self.manager);self.assertEqual(self.client.post(url,{'confirm_read_only_check':True},format='json').status_code,403)
        self.client.force_authenticate(self.comptroller)
        with patch.dict(os.environ,CONFIG):
            self.assertEqual(self.client.post(url,{},format='json').status_code,400)
            self.assertEqual(self.client.post(url,{'confirm_read_only_check':True},format='json').status_code,400)
        self.check_finish(self.check_start())
        response=self.client.get(f'/api/signing-reviews/{self.plan.id}/sandbox-package/')
        self.assertEqual(response.status_code,200);self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertEqual(response.json()['attempt']['observations'][0]['evidence']['outcome'],'MATCHED')
        self.assertNotIn('documentBase64',response.content.decode())

    def test_account_configuration_changed_during_reads_blocks(self):
        self.known_draft();data=iter(self.readings());count=0
        def hook(*args,**kwargs):
            nonlocal count
            count+=1
            if count==4:os.environ['GECC_DOCUSIGN_CLIENT_SECRET']='synthetic-replacement-secret'
            return next(data)
        result,_=self.check_finish(self.check_start(),hook=hook)
        self.assertEqual(result['status'],'SANDBOX_RECONCILIATION_BLOCKED')

    def test_disabled_actor_during_reads_blocks(self):
        self.known_draft();data=iter(self.readings());count=0
        def hook(*args,**kwargs):
            nonlocal count
            count+=1
            if count==4:type(self.comptroller).objects.filter(pk=self.comptroller.id).update(is_active=False)
            return next(data)
        result,_=self.check_finish(self.check_start(),hook=hook)
        self.assertEqual(result['status'],'SANDBOX_RECONCILIATION_BLOCKED')

    def test_mismatch_category_exposed_without_provider_error_details(self):
        self.known_draft();data=self.readings()
        data[1]['signers'][0]['tabs']['signHereTabs'][0]['xPosition']='999'
        result,_=self.check_finish(self.check_start(),data)
        self.assertEqual(result['blockers'],['A field label, document assignment, page or position differs.'])
        self.assertEqual(SandboxObservation.objects.get().evidence['blockers'],result['blockers'])
        with patch('core.sandbox.validated_evidence',side_effect=ValidationError('private-provider-body-and-token')):
            result,_=self.check_finish(self.check_start())
        self.assertEqual(result['blockers'],['Provider draft metadata differs from the saved sandbox package.'])
        self.assertNotIn('private-provider',json.dumps(result))
        self.assertNotIn('private-provider',json.dumps(list(SandboxObservation.objects.values('evidence'))))
