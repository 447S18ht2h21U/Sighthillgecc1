import json
import logging
import os
import time
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from django.test import TestCase, override_settings
from django.db import DatabaseError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from . import tests as foundation
from .models import DocusignChallenge, DocusignVerification, AuditEvent, Outbox
from .log_filters import CallbackLogFilter
from .docusign import begin, finish, readiness, configuration, request_json

ENV={'GECC_DOCUSIGN_CLIENT_ID':'11111111-1111-4111-8111-111111111111',
     'GECC_DOCUSIGN_ACCOUNT_ID':'22222222-2222-4222-8222-222222222222',
     'GECC_DOCUSIGN_CLIENT_SECRET':'synthetic-client-secret-for-tests',
     'GECC_DOCUSIGN_REDIRECT_URI':'http://localhost:8000/api/docusign/callback/'}
TOKENS={'access_token':'synthetic-access-token-for-tests','refresh_token':'synthetic-refresh-token-for-tests','expires_in':3600,'token_type':'Bearer'}
INFO={'sub':'33333333-3333-4333-8333-333333333333','accounts':[{'account_id':ENV['GECC_DOCUSIGN_ACCOUNT_ID'],'account_name':'Synthetic Sandbox','base_uri':'https://demo.docusign.net'}]}

@override_settings(DEBUG=True)
class DocusignTests(TestCase):
    setUp = foundation.FoundationTests.setUp
    def configured(self):
        return patch.dict(os.environ,ENV)
    def start(self,actor=None,session='synthetic-session'):
        response=begin(actor or self.comptroller,session)
        return parse_qs(urlsplit(response['authorization_url']).query)['state'][0]
    def test_begin_is_sandbox_bound_and_audited(self):
        with self.configured():
            result=begin(self.comptroller,'synthetic-session');parts=urlsplit(result['authorization_url']);query=parse_qs(parts.query)
            self.assertEqual(parts.netloc,'account-d.docusign.com');self.assertEqual(query['scope'],['signature'])
            self.assertEqual(query['response_type'],['code']);self.assertEqual(query['redirect_uri'],[ENV['GECC_DOCUSIGN_REDIRECT_URI']])
            self.assertNotIn(ENV['GECC_DOCUSIGN_CLIENT_SECRET'],result['authorization_url'])
            self.assertNotEqual(DocusignChallenge.objects.get().state_digest,query['state'][0])
            self.assertEqual(AuditEvent.objects.count(),Outbox.objects.count())
    def test_missing_and_malformed_config_fail_closed(self):
        for key in ENV:
            with self.subTest(key=key),self.configured(),patch.dict(os.environ,{key:''}):
                self.assertFalse(readiness(self.comptroller)['ready_to_verify'])
                with self.assertRaises(ValidationError):begin(self.comptroller,'session')
        with self.configured(),patch.dict(os.environ,{'GECC_DOCUSIGN_REDIRECT_URI':'http://malicious.example/api/docusign/callback/'}):
            self.assertTrue(configuration()['blockers'])
    def test_configuration_disables_production(self):
        with self.configured(),override_settings(DEBUG=False):
            self.assertFalse(readiness(self.comptroller)['ready_to_verify'])
            with self.assertRaises(ValidationError):self.start()
    def test_verifies_explicit_account_and_discards_tokens(self):
        with self.configured(),patch('core.docusign.request_json',side_effect=[TOKENS,INFO]) as transport:
            proof=finish(self.comptroller,'synthetic-session',self.start(),'synthetic-code')
            self.assertEqual(proof.identity['purpose'],'ACCOUNT_VERIFICATION_ONLY');self.assertFalse(proof.identity['tokens_retained'])
            self.assertEqual(transport.call_count,2);self.assertIn('authorization_expires_at',proof.identity)
            public=readiness(self.comptroller);self.assertFalse(public['send_available']);self.assertEqual(public['verification']['account_name'],'Synthetic Sandbox')
            evidence=json.dumps(list(AuditEvent.objects.values('payload')))+json.dumps(proof.identity)
            for secret in [ENV['GECC_DOCUSIGN_CLIENT_SECRET'],TOKENS['access_token'],TOKENS['refresh_token'],'synthetic-code']:
                self.assertNotIn(secret,evidence);self.assertNotIn(secret,json.dumps(public))
    def test_replay_wrong_session_and_wrong_actor_rejected(self):
        with self.configured():
            state=self.start()
            with patch('core.docusign.request_json') as transport:
                with self.assertRaises(ValidationError):finish(self.comptroller,'wrong-session',state,'code')
                with self.assertRaises(PermissionDenied):finish(self.manager,'synthetic-session',state,'code')
                transport.assert_not_called()
            with patch('core.docusign.request_json',side_effect=[TOKENS,INFO]):finish(self.comptroller,'synthetic-session',state,'code')
            with patch('core.docusign.request_json') as transport:
                with self.assertRaises(ValidationError):finish(self.comptroller,'synthetic-session',state,'code')
                transport.assert_not_called()
    def test_expired_or_changed_configuration_state(self):
        with self.configured():
            state=self.start();DocusignChallenge.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
            with self.assertRaises(ValidationError):finish(self.comptroller,'synthetic-session',state,'code')
            state=self.start()
            with patch.dict(os.environ,{'GECC_DOCUSIGN_CLIENT_SECRET':'changed-synthetic-secret'}),self.assertRaises(ValidationError):finish(self.comptroller,'synthetic-session',state,'code')
    def test_declined_authorization_is_consumed(self):
        with self.configured():
            state=self.start()
            with self.assertRaises(ValidationError):finish(self.comptroller,'synthetic-session',state,None,'access_denied')
            self.assertIsNotNone(DocusignChallenge.objects.get().consumed_at)
    def test_wrong_account_production_and_malformed_provider_rejected(self):
        bad_accounts=[{**INFO,'accounts':[{**INFO['accounts'][0],'base_uri':'https://na4.docusign.net'}]},
                      {**INFO,'accounts':[{**INFO['accounts'][0],'account_id':'other-account'}]},
                      {**INFO,'accounts':INFO['accounts']*2}, {**INFO,'sub':'invalid'}, {**INFO,'accounts':None}]
        with self.configured():
            for info in bad_accounts:
                with self.subTest(info=info),patch('core.docusign.request_json',side_effect=[TOKENS,info]),self.assertRaises(ValidationError):finish(self.comptroller,'synthetic-session',self.start(),'code')
            for tokens in [{**TOKENS,'expires_in':True},{**TOKENS,'expires_in':0},{**TOKENS,'token_type':'invalid'},{**TOKENS,'access_token':None}]:
                with patch('core.docusign.request_json',return_value=tokens),self.assertRaises(ValidationError):finish(self.comptroller,'synthetic-session',self.start(),'code')
        self.assertEqual(DocusignVerification.objects.count(),0)
    def test_provider_failure_cannot_reuse_state(self):
        with self.configured():
            state=self.start()
            with patch('core.docusign.request_json',side_effect=ValidationError('provider failed')),self.assertRaises(ValidationError):finish(self.comptroller,'synthetic-session',state,'code')
            self.assertIsNotNone(DocusignChallenge.objects.get().consumed_at)
            with patch('core.docusign.request_json') as transport:
                with self.assertRaises(ValidationError):finish(self.comptroller,'synthetic-session',state,'code')
                transport.assert_not_called()
    def test_evidence_database_immutable_and_audit_atomic(self):
        with self.configured(),patch('core.docusign.request_json',side_effect=[TOKENS,INFO]):proof=finish(self.comptroller,'synthetic-session',self.start(),'code')
        with self.assertRaises(DatabaseError),transaction.atomic():DocusignVerification.objects.filter(pk=proof.pk).update(identity={})
        with self.assertRaises(DatabaseError),transaction.atomic():DocusignVerification.objects.filter(pk=proof.pk).delete()
        with self.configured(),patch('core.docusign.request_json',side_effect=[TOKENS,INFO]):
            state=self.start()
            with patch('core.docusign.audit',side_effect=RuntimeError('audit failed')),self.assertRaises(RuntimeError):finish(self.comptroller,'synthetic-session',state,'code')
        self.assertEqual(DocusignVerification.objects.count(),1)
    def test_api_permissions_csrf_and_private_responses(self):
        self.client.force_authenticate(self.sales)
        self.assertEqual(self.client.get('/api/docusign/status/').status_code,403)
        self.client.force_authenticate(user=None);self.client.force_login(self.comptroller)
        session=self.client.session;session['last_activity']=time.time();session.save()
        with self.configured():
            response=self.client.post('/api/docusign/connect/',{},format='json');self.assertEqual(response.status_code,200)
            self.assertEqual(response['Referrer-Policy'],'no-referrer');self.assertIn('no-store',response['Cache-Control'])
            state=parse_qs(urlsplit(response.json()['authorization_url']).query)['state'][0]
            with patch('core.docusign.request_json',side_effect=[TOKENS,INFO]):response=self.client.get('/api/docusign/callback/',{'state':state,'code':'synthetic-code'})
            self.assertEqual(response.status_code,200);self.assertEqual(response.json()['status'],'SANDBOX_ACCOUNT_VERIFIED')
            self.assertNotIn('synthetic-code',response.content.decode())
        from rest_framework.test import APIClient
        client=APIClient(enforce_csrf_checks=True);client.force_login(self.comptroller);session=client.session;session['last_activity']=time.time();session.save()
        self.assertEqual(client.post('/api/docusign/connect/',{},format='json').status_code,403)
    def test_callback_unexpected_errors_are_redacted(self):
        self.client.force_authenticate(self.comptroller)
        with patch('core.docusign.finish',side_effect=RuntimeError('secret-code-access-token')):
            response=self.client.get('/api/docusign/callback/',{'code':'secret-code-access-token'})
        self.assertEqual(response.status_code,502);self.assertNotIn('secret-code',response.content.decode())
    def test_callback_log_redaction(self):
        record=logging.LogRecord('django.server',logging.INFO,'',0,'"%s" %s',('GET /api/docusign/callback/?code=private-code&state=private-state HTTP/1.1','200'),None)
        CallbackLogFilter().filter(record);message=record.getMessage()
        self.assertNotIn('private-code',message);self.assertNotIn('private-state',message);self.assertIn('[redacted]',message)
    def test_transport_is_fixed_origin_bounded_and_redacts_errors(self):
        with patch('core.docusign.build_opener') as opener:
            response=opener.return_value.open.return_value.__enter__.return_value;response.read.return_value=json.dumps(TOKENS).encode()
            self.assertEqual(request_json('/oauth/token','Basic synthetic',{'code':'code'}),TOKENS)
            request=opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url,'https://account-d.docusign.com/oauth/token');self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'],8)
            response.read.return_value=b'x'*262145
            with self.assertRaises(ValidationError):request_json('/oauth/token','Basic synthetic',{})
            opener.return_value.open.side_effect=RuntimeError('private-token')
            with self.assertRaises(ValidationError) as error:request_json('/oauth/userinfo','Bearer synthetic')
            self.assertNotIn('private-token',str(error.exception))
        with self.assertRaises(ValidationError):request_json('https://malicious.example','Bearer synthetic')
