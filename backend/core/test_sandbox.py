import base64
import copy
import json
import os
from io import BytesIO
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
from uuid import uuid4
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from pypdf import PdfReader
from rest_framework.exceptions import PermissionDenied, ValidationError
from . import docusign, sandbox
from .models import AuditEvent, DocusignChallenge, Outbox, SandboxAttempt, SandboxPackage
from .services import change_project_state, revise, transition
from .signing import prepare
from . import test_signing as signing_tests
from . import tests as foundation

CONFIG = {'GECC_DOCUSIGN_CLIENT_ID':'11111111-1111-4111-8111-111111111111',
          'GECC_DOCUSIGN_ACCOUNT_ID':'22222222-2222-4222-8222-222222222222',
          'GECC_DOCUSIGN_CLIENT_SECRET':'synthetic-client-secret',
          'GECC_DOCUSIGN_REDIRECT_URI':'http://localhost:8000/api/docusign/callback/'}

@override_settings(DEBUG=True)
class SandboxTests(TestCase):
    setUp = foundation.FoundationTests.setUp
    edit_submit = foundation.FoundationTests.edit_submit
    approve = foundation.FoundationTests.approve
    setup_review = signing_tests.SigningTests.setup_review
    def setup_package(self, completion=False):
        self.setup_review()
        data={**self.input}
        if completion:
            data.update(group='COMPLETION_NON_FINANCED', gecc_signer=str(self.comptroller.id), substitute_reason='Synthetic unavailable scenario')
        self.plan,_=prepare(self.manager,self.approved.id,data)
        self.package,_=sandbox.prepare_package(self.manager,self.plan.id)
    def start(self):
        with patch.dict(os.environ,CONFIG):
            result=sandbox.begin_draft(self.comptroller,'synthetic-session',self.package.id,True)
        return parse_qs(urlsplit(result['authorization_url']).query)['state'][0]
    def provider_responses(self):
        eid=str(uuid4());expected=self.package.payload['envelope_preview']
        return [{'envelopeId':eid,'status':'created'}, {'envelopeId':eid,'status':'created'},
                copy.deepcopy(expected['recipients']), {'envelopeDocuments':copy.deepcopy(expected['documents'])}]
    def oauth_responses(self):
        return [{'access_token':'synthetic-access-token','refresh_token':'synthetic-refresh-token','token_type':'Bearer','expires_in':3600},
                {'sub':'33333333-3333-4333-8333-333333333333','accounts':[{'account_id':CONFIG['GECC_DOCUSIGN_ACCOUNT_ID'],'base_uri':docusign.BASE_URI,'account_name':'Synthetic GECC'}]}]
    def finish(self,state,responses=None):
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=self.oauth_responses()),patch('core.sandbox.provider',side_effect=responses or self.provider_responses()) as provider:
            result=docusign.finish(self.comptroller,'synthetic-session',state,'synthetic-code')
        return result,provider
    def test_package_exact_reviewed_names_and_native_unsigned_fields(self):
        self.setup_package()
        self.assertEqual(len(self.package.payload['documents']),2)
        for entry in self.package.payload['documents']:
            reader=PdfReader(BytesIO(base64.b64decode(entry['documentBase64'])))
            fields=reader.get_fields()
            self.assertEqual(fields['customer_printed_name']['/V'],'Authorized Customer')
            self.assertEqual(fields['gecc_representative_name']['/V'],'Review Manager')
            self.assertEqual(fields['gecc_role']['/V'],'Sales Manager')
            for key in ['customer_signature','gecc_signature']:
                self.assertEqual(fields[key]['/FT'],'/Sig');self.assertFalse(fields[key].get('/V'))
            text='\n'.join(p.extract_text() for p in reader.pages)
            self.assertIn('SANDBOX TEST - DO NOT SIGN',text)
            self.assertIn('Sandbox routing review',text)
            self.assertIn('Approved project detail',text)
        self.assertFalse(sandbox.describe(self.package)['send_available'])
        self.assertNotIn('documentBase64',json.dumps(sandbox.describe(self.package)))
    def test_completion_substitute_retained_without_false_completion(self):
        self.setup_package(True)
        entry=self.package.payload['documents'][0]
        fields=PdfReader(BytesIO(base64.b64decode(entry['documentBase64']))).get_fields()
        self.assertEqual(fields['gecc_role']['/V'],'Comptroller')
        self.assertEqual(fields['gecc_substitute_reason']['/V'],'Synthetic unavailable scenario')
        self.assertFalse(fields['completion_date'].get('/V'))
        self.assertEqual([s['routingOrder'] for s in self.package.payload['envelope_preview']['recipients']['signers']],['2','1'])
    def test_idempotent_audit_atomic_and_database_immutable(self):
        self.setup_package();count=AuditEvent.objects.count()
        again,created=sandbox.prepare_package(self.manager,self.plan.id)
        self.assertFalse(created);self.assertEqual(again.id,self.package.id);self.assertEqual(count,AuditEvent.objects.count())
        with self.assertRaises(DatabaseError),transaction.atomic():SandboxPackage.objects.filter(pk=self.package.id).update(payload={})
        with self.assertRaises(DatabaseError),transaction.atomic():SandboxPackage.objects.filter(pk=self.package.id).delete()
        other,_=prepare(self.manager,self.approved.id,{**self.input,'customer_name':'Other Customer'})
        with patch('core.sandbox.audit',side_effect=RuntimeError('audit unavailable')),self.assertRaises(RuntimeError):sandbox.prepare_package(self.manager,other.id)
        self.assertEqual(SandboxPackage.objects.count(),1)
        self.assertEqual(AuditEvent.objects.count(),Outbox.objects.count())
    def test_stale_changed_and_cancelled_rejected(self):
        self.setup_package();self.manager.email='changed@example.invalid';self.manager.save()
        with self.assertRaises(ValidationError):sandbox.prepare_package(self.comptroller,self.plan.id)
        with patch.dict(os.environ,CONFIG),self.assertRaises(ValidationError):sandbox.begin_draft(self.comptroller,'session',self.package.id,True)
        # Historical package bytes remain readable, but cannot be sent to Docusign.
        sandbox.validate_package(self.package,check_current=False)
    def test_package_integrity_rejects_memory_tamper(self):
        self.setup_package();self.package.payload['documents'][0]['pdf_sha256']='0'*64
        with self.assertRaises(ValidationError):sandbox.validate_package(self.package)
    def test_names_not_silently_replaced_with_detail(self):
        self.setup_review();plan,_=prepare(self.manager,self.approved.id,{**self.input,'customer_name':'W'*200})
        with self.assertRaisesMessage(ValidationError,'does not fit'):sandbox.prepare_package(self.manager,plan.id)
        self.assertFalse(SandboxPackage.objects.exists())
    def test_local_permissions_explicit_confirmation_and_production_disabled(self):
        self.setup_package()
        with self.assertRaises(PermissionDenied):sandbox.begin_draft(self.manager,'session',self.package.id,True)
        with patch.dict(os.environ,CONFIG),self.assertRaises(ValidationError):sandbox.begin_draft(self.comptroller,'session',self.package.id,'true')
        with override_settings(DEBUG=False),self.assertRaises(ValidationError):sandbox.prepare_package(self.manager,self.plan.id)
    def test_create_and_inspect_exact_draft_no_tokens_stored(self):
        self.setup_package();state=self.start();result,provider=self.finish(state)
        self.assertEqual(result['status'],'SANDBOX_DRAFT_VALIDATED');self.assertEqual(provider.call_count,4)
        payload=provider.call_args_list[0].kwargs['payload']
        self.assertEqual(payload['status'],'created');self.assertEqual(len(payload['documents']),2)
        self.assertTrue(all('documentBase64' in d for d in payload['documents']))
        attempt=SandboxAttempt.objects.get(package=self.package)
        self.assertEqual(payload['transactionId'],str(attempt.id));self.assertEqual(attempt.state,'DRAFT_VALIDATED')
        stored=json.dumps(list(AuditEvent.objects.values('payload')))+json.dumps(attempt.evidence)+json.dumps(self.package.payload)
        for secret in ['synthetic-access-token','synthetic-refresh-token','synthetic-client-secret','synthetic-code']:
            self.assertNotIn(secret,stored)
        self.assertTrue(attempt.evidence['visual_review_required'])
        with patch.dict(os.environ,CONFIG),self.assertRaises(ValidationError):sandbox.begin_draft(self.comptroller,'synthetic-session',self.package.id,True)
        with patch.dict(os.environ,CONFIG),patch('core.sandbox.provider') as remote,self.assertRaises(ValidationError):docusign.finish(self.comptroller,'synthetic-session',state,'synthetic-code')
        remote.assert_not_called()
    def test_ambiguous_create_never_retried(self):
        self.setup_package();state=self.start()
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=self.oauth_responses()),patch('core.sandbox.provider',side_effect=TimeoutError('synthetic-token-in-provider-error')),self.assertRaises(ValidationError) as error:
            docusign.finish(self.comptroller,'synthetic-session',state,'synthetic-code')
        self.assertNotIn('synthetic-token',str(error.exception))
        attempt=SandboxAttempt.objects.get(package=self.package);self.assertEqual(attempt.state,'RECONCILIATION_REQUIRED')
        with patch.dict(os.environ,CONFIG),self.assertRaises(ValidationError):sandbox.begin_draft(self.comptroller,'session',self.package.id,True)
    def test_failed_inspection_preserves_envelope_id(self):
        self.setup_package();state=self.start();responses=self.provider_responses();eid=responses[0]['envelopeId'];responses[1]['status']='sent'
        with self.assertRaises(ValidationError):self.finish(state,responses)
        attempt=SandboxAttempt.objects.get(package=self.package)
        self.assertEqual(attempt.envelope_id,eid);self.assertEqual(attempt.state,'RECONCILIATION_REQUIRED')
    def test_recipient_tab_and_document_drift_rejected(self):
        self.setup_package()
        for change in ['routing','tabs','documents','optional','extra']:
            r=self.provider_responses();expected=self.package.payload['envelope_preview']
            if change=='routing':r[2]['signers'][0]['routingOrder']='2'
            elif change=='tabs':r[2]['signers'][0]['tabs']['signHereTabs'][0]['xPosition']='999'
            elif change=='documents':r[3]['envelopeDocuments'][0]['name']='other.pdf'
            elif change=='optional':r[2]['signers'][0]['tabs']['signHereTabs'][0]['optional']='true'
            else:r[2]['carbonCopies']=[{'email':'extra@example.invalid'}]
            with self.subTest(change=change),self.assertRaises(ValidationError):sandbox.validated_evidence(expected,r[1],r[2],r[3],r[0]['envelopeId'])
    def test_latest_challenge_wins_and_changed_review_blocks_before_post(self):
        self.setup_package();old=self.start();new=self.start()
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=self.oauth_responses()),patch('core.sandbox.provider') as remote,self.assertRaises(ValidationError):docusign.finish(self.comptroller,'synthetic-session',old,'code')
        remote.assert_not_called()
        prepare(self.manager,self.approved.id,{**self.input,'customer_name':'Replacement Customer'})
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=self.oauth_responses()),patch('core.sandbox.provider') as remote,self.assertRaises(ValidationError):docusign.finish(self.comptroller,'synthetic-session',new,'code')
        remote.assert_not_called()
    def test_api_scope_download_and_no_bytes_in_status(self):
        self.setup_package();self.client.force_authenticate(self.manager)
        url=f'/api/signing-reviews/{self.plan.id}/sandbox-package/'
        response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertNotIn('documentBase64',response.content.decode())
        self.assertEqual(self.client.post(url,{},format='json').status_code,200)
        path=response.json()['documents'][0]['download_url'];download=self.client.get(path)
        self.assertEqual(download.status_code,200);self.assertEqual(download['Cache-Control'],'private, no-store')
        self.client.force_authenticate(self.other);self.assertEqual(self.client.get(url).status_code,404);self.assertEqual(self.client.get(path).status_code,404)
        self.client.force_authenticate(self.sales);self.assertEqual(self.client.post(url,{},format='json').status_code,403)
    def test_transport_rejects_non_draft_and_arbitrary_reads(self):
        with self.assertRaises(ValidationError):sandbox.provider(CONFIG['GECC_DOCUSIGN_ACCOUNT_ID'],'','token',payload={'status':'sent'})
        with self.assertRaises(ValidationError):sandbox.provider(CONFIG['GECC_DOCUSIGN_ACCOUNT_ID'],str(uuid4()),'token',resource='/views/sender')
        with patch('core.sandbox.build_opener') as opener:
            opener.return_value.open.side_effect=RuntimeError('private-access-token')
            with self.assertRaises(ValidationError) as error:sandbox.provider(CONFIG['GECC_DOCUSIGN_ACCOUNT_ID'],'','token',payload={'status':'created'})
            self.assertNotIn('private-access-token',str(error.exception))
            self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'],12)

    def test_cancellation_and_revision_block_callback_before_provider_create(self):
        self.setup_package();state=self.start()
        change_project_state(self.comptroller,self.project.id,'cancel','Synthetic cancellation','APPROVED')
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=self.oauth_responses()),patch('core.sandbox.provider') as remote,self.assertRaises(ValidationError):
            docusign.finish(self.comptroller,'synthetic-session',state,'code')
        remote.assert_not_called()
        change_project_state(self.comptroller,self.project.id,'reopen','Synthetic reopen','CANCELLED')
        state=self.start()
        item=revise(self.sales,self.project.id,'Synthetic change',str(self.approved.id))
        item=transition(self.sales,item.id,'submit',0);transition(self.comptroller,item.id,'approve',item.edit_sequence)
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=self.oauth_responses()),patch('core.sandbox.provider') as remote,self.assertRaises(ValidationError):
            docusign.finish(self.comptroller,'synthetic-session',state,'code')
        remote.assert_not_called()
    def test_wrong_account_never_calls_sandbox_provider(self):
        self.setup_package();state=self.start();oauth=self.oauth_responses();oauth[1]['accounts'][0]['account_id']=str(uuid4())
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=oauth),patch('core.sandbox.provider') as remote,self.assertRaises(ValidationError):
            docusign.finish(self.comptroller,'synthetic-session',state,'code')
        remote.assert_not_called();self.assertEqual(SandboxAttempt.objects.get(package=self.package).state,'AUTH_PENDING')
    def test_draft_api_session_and_confirmation_required(self):
        self.setup_package();url=f'/api/sandbox-packages/{self.package.id}/connect-draft/'
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.post(url,{'confirm_unsent_sandbox_draft':True},format='json').status_code,403)
        self.client.force_authenticate(self.comptroller)
        with patch.dict(os.environ,CONFIG):
            self.assertEqual(self.client.post(url,{},format='json').status_code,400)
            self.assertEqual(self.client.post(url,{'confirm_unsent_sandbox_draft':True},format='json').status_code,400)
        self.assertFalse(SandboxAttempt.objects.exists())

    def test_first_use_missing_package_returns_parseable_json_null(self):
        self.setup_review();plan,_=prepare(self.manager,self.approved.id,self.input)
        self.client.force_authenticate(self.manager)
        response=self.client.get(f'/api/signing-reviews/{plan.id}/sandbox-package/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.content,b'null')
        self.assertIsNone(response.json())
        self.assertEqual(response['Cache-Control'],'private, no-store')
