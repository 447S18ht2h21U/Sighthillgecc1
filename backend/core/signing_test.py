"""Explicitly approved fictional signing tests: fixed sandbox origin, one send attempt."""
import base64
import copy
import hashlib
import json
import os
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, build_opener
from uuid import UUID
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.debug import sensitive_variables
from pypdf import PdfReader
from rest_framework.exceptions import PermissionDenied, ValidationError
from . import docusign, release, sandbox, signing
from .documents import canonical_hash, render_pdf
from .models import (Project, ReleasePackage, SigningTestPackage, SigningTestDecision,
                     SigningTestAttempt, SigningTestObservation, SigningTestDocument, User)
from .services import authorize, audit

VERSION = 'sandbox-signing-0.1'
OP_SEND = 'SANDBOX_SIGNING_SEND'
OP_READ = 'SANDBOX_SIGNING_READ'
STATUSES = {'sent', 'delivered', 'signed', 'completed', 'declined', 'voided'}
MAX_RETAINED_BYTES = 24 * 1024 * 1024


def development():
    if not settings.DEBUG:
        raise ValidationError('Signing tests are available only in local development. Production sending is disabled.')


def address(value):
    if not isinstance(value, str): raise ValidationError('Enter a test email address.')
    value = value.strip().lower()
    try: validate_email(value)
    except DjangoValidationError: raise ValidationError('Enter a valid controlled test email address.')
    domain = value.rsplit('@',1)[-1]
    if domain in {'example.com','example.net','example.org','localhost'} or domain.endswith(('.invalid','.test','.example','.localhost')):
        raise ValidationError('Fictional email addresses cannot receive signing-test invitations.')
    return value


def sending_enabled():
    if os.getenv('GECC_SANDBOX_SIGNING_SEND_ENABLED')!='1':
        raise ValidationError('Sandbox signing-test sending is disabled. Enable it explicitly on the backend after choosing controlled test emails.')


def policy():
    development()
    raw = os.getenv('GECC_SANDBOX_TEST_EMAILS','')
    if not raw or len(raw)>2000:
        raise ValidationError('Configure GECC_SANDBOX_TEST_EMAILS on the backend with the two test email addresses you control.')
    allowed = sorted({address(v) for v in raw.split(',')})
    if not 2 <= len(allowed) <= 10:
        raise ValidationError('Configure between two and ten distinct controlled sandbox test email addresses.')
    return allowed


def require_source(source):
    # Reload relations: approval/evidence/role changes must be checked against current DB state.
    source = ReleasePackage.objects.select_related('plan__msr__project').get(pk=source.id)
    if release.status(source)['status'] != 'APPROVED':
        raise ValidationError('The source release package needs a current independent approval.')
    decision = source.decisions.order_by('-created_at','-id').first()
    evidence = release.evidence_for(source.plan)
    if not any(word in evidence.data['source_reference'].lower() for word in ['simulated','synthetic']):
        raise ValidationError('Signing tests require an explicitly simulated or synthetic verification reference.')
    return source, decision, evidence


@transaction.atomic
def prepare(actor, source_id, data):
    development();docusign.authorize(actor)
    if not isinstance(data,dict) or data.get('fictional_project_confirmed') is not True or data.get('emails_controlled') is not True:
        raise ValidationError('Confirm the project is fictional and both test email addresses are controlled by you.')
    reference = ReleasePackage.objects.select_related('plan__msr').get(pk=source_id)
    Project.objects.select_for_update().get(pk=reference.plan.msr.project_id)
    source, approval, evidence = require_source(reference)
    emails = [address(data.get('customer_email')), address(data.get('gecc_email'))]
    if len(set(emails))!=2 or not set(emails).issubset(policy()):
        raise ValidationError('Use two distinct email addresses from the configured sandbox test allowlist.')
    note = signing.required_text(data,'test_note',2000)
    bound = canonical_hash({'source_digest':source.digest,'approval_id':str(approval.id),'emails':emails,'note':note,'version':VERSION})
    existing = SigningTestPackage.objects.filter(source=source,payload__binding_digest=bound).first()
    if existing: validate(existing);return existing,False
    review = copy.deepcopy(source.plan.review)
    review['customer']['email'], review['gecc']['email'] = emails
    entries=[];docs=[];total=0
    for item in review['documents']:
        content, values, template_hash = render_pdf(item['kind'],source.plan.msr,timezone.now(),
            release_context={'review':review,'evidence':evidence.data},signing_test=True)
        if template_hash!=item['template_sha256']:
            raise ValidationError('The approved template changed; prepare a new recipient review.')
        total+=len(content)
        if total>sandbox.MAX_PDF_BYTES: raise ValidationError('Signing-test package exceeds its size limit.')
        filename=f'{source.plan.msr.project.code}-V{source.plan.msr.number}-{item["kind"]}-SIGNING-TEST.pdf'
        entries.append({'kind':item['kind'],'filename':filename,'pdf_sha256':hashlib.sha256(content).hexdigest(),
                        'template_sha256':template_hash,'documentBase64':base64.b64encode(content).decode()})
        docs.append(SimpleNamespace(content=content,filename=filename))
    payload={'version':VERSION,'purpose':'FICTIONAL_SANDBOX_SIGNING_TEST','binding_digest':bound,
             'source_digest':source.digest,'source_approval_id':str(approval.id),'test_note':note,
             'review':review,'documents':entries,
             'envelope_preview':signing.envelope_preview(docs,review['customer'],review['gecc'],source.plan.group=='COMMERCIAL')}
    package=SigningTestPackage.objects.create(source=source,created_by=actor,payload=payload,digest=canonical_hash(payload))
    audit(actor,'signing_test.package_prepared',source.plan.msr.project_id,{'package_id':str(package.id),'digest':package.digest,
          'source_id':str(source.id),'test_recipients':emails,'pdf_hashes':[d['pdf_sha256'] for d in entries]})
    return package,True


def validate(package, current=True):
    development()
    p=package.payload
    if canonical_hash(p)!=package.digest or p.get('version')!=VERSION or p.get('purpose')!='FICTIONAL_SANDBOX_SIGNING_TEST':
        raise ValidationError('Signing-test package integrity verification failed.')
    for d in p['documents']:
        if hashlib.sha256(base64.b64decode(d['documentBase64'],validate=True)).hexdigest()!=d['pdf_sha256']:
            raise ValidationError('Signing-test PDF integrity verification failed.')
    if current:
        source, approval, _ = require_source(package.source)
        if source.digest!=p['source_digest'] or str(approval.id)!=p['source_approval_id']:
            raise ValidationError('Source release approval changed; prepare and approve a new signing-test package.')
        emails={p['review']['customer']['email'],p['review']['gecc']['email']}
        if len(emails)!=2 or not emails.issubset(policy()):
            raise ValidationError('Signing-test email allowlist changed.')


def approval_for(package):
    validate(package)
    decision=package.decisions.order_by('-created_at','-id').first()
    if not decision or decision.decision!='APPROVED':
        raise ValidationError('A separate independent signing-test approval is required.')
    expected=canonical_hash({'package_digest':package.digest,'actor':str(decision.created_by_id),'decision':decision.decision,'note':decision.note})
    if expected!=decision.digest:raise ValidationError('Signing-test approval integrity verification failed.')
    actor=User.objects.get(pk=decision.created_by_id)
    authorize(actor,package.source.plan.msr.project,approval=True)
    if not actor.is_active:raise PermissionDenied('The signing-test reviewer is inactive.')
    return decision


@transaction.atomic
def decide(actor, package_id, data):
    development()
    reference=SigningTestPackage.objects.select_related('source__plan__msr').get(pk=package_id)
    Project.objects.select_for_update().get(pk=reference.source.plan.msr.project_id)
    package=SigningTestPackage.objects.select_related('source__plan__msr__project').get(pk=package_id)
    authorize(actor,package.source.plan.msr.project,approval=True)
    if not actor.is_active:raise PermissionDenied('Inactive signing-test reviewer.')
    if not isinstance(data,dict) or not isinstance(data.get('decision'),str) or data.get('decision') not in {'APPROVED','REVOKED'}:
        raise ValidationError('Choose approve or revoke.')
    note=signing.required_text(data,'note',2000)
    if data['decision']=='APPROVED':
        validate(package)
        evidence=release.evidence_for(package.source.plan)
        if actor.id in {package.created_by_id,evidence.created_by_id}:
            raise PermissionDenied('Another authorized person must independently approve the signing test.')
        if data.get('exact_test_reviewed') is not True:
            raise ValidationError('Confirm review of the exact signing-test PDFs, controlled emails, names and routing.')
    previous=package.decisions.order_by('-created_at','-id').first()
    if previous and previous.decision==data['decision'] and previous.note==note and previous.created_by_id==actor.id:return previous,False
    digest=canonical_hash({'package_digest':package.digest,'actor':str(actor.id),'decision':data['decision'],'note':note})
    result=SigningTestDecision.objects.create(package=package,created_by=actor,decision=data['decision'],note=note,digest=digest)
    audit(actor,'signing_test.decision_recorded',package.source.plan.msr.project_id,{'package_id':str(package.id),'decision_id':str(result.id),'decision':result.decision,'digest':digest})
    return result,True


def require_no_other_send(package):
    # The project lock serializes this guard with other signing tests for the same workflow.
    pending=SigningTestAttempt.objects.filter(
        package__source__plan__msr__project_id=package.source.plan.msr.project_id,
        package__source__plan__group=package.source.plan.group,
        first_send_started_at__isnull=False).exclude(state__in=['DECLINED','VOIDED','COMPLETED_RETAINED'])
    if pending.exists():
        raise ValidationError('An earlier signing test for this project workflow is sent, pending or uncertain. Check it before authorizing another send.')


def eligibility(package):
    try:
        approval_for(package)
        return []
    except (ValidationError,PermissionDenied):
        return ['The signing-test package, source verification or independent approval is no longer eligible.']


@transaction.atomic
def begin(actor, session_key, package_id, operation, confirmed):
    development();docusign.authorize(actor)
    if confirmed is not True or operation not in {OP_SEND,OP_READ}:
        raise ValidationError('Explicit sandbox send or read confirmation is required.')
    reference=SigningTestPackage.objects.select_related('source__plan__msr').get(pk=package_id)
    Project.objects.select_for_update().get(pk=reference.source.plan.msr.project_id)
    package=SigningTestPackage.objects.select_related('source__plan__msr__project').get(pk=package_id)
    config=docusign.configuration()
    if config['blockers']:raise ValidationError({'configuration':config['blockers']})
    if operation==OP_SEND:
        sending_enabled()
        require_no_other_send(package)
        decision=approval_for(package)
        attempt,_=SigningTestAttempt.objects.get_or_create(package=package,defaults={'actor':actor,'account_id':config['account_id']})
        attempt=SigningTestAttempt.objects.select_for_update().get(pk=attempt.id)
        if attempt.state!='AUTH_PENDING' or attempt.first_send_started_at or attempt.actor_id!=actor.id:
            raise ValidationError('This package already has a send attempt. Never create or send a duplicate after an uncertain result.')
    else:
        validate(package,current=False)
        attempt=SigningTestAttempt.objects.select_for_update().filter(package=package).first()
        if not attempt or not attempt.envelope_id or not attempt.first_send_started_at or attempt.state=='NETWORK_STARTED':
            raise ValidationError('No known sent signing-test envelope is available to read.')
        decision=None
    if attempt.account_id!=config['account_id']:raise ValidationError('The signing test belongs to a different sandbox account.')
    context={'operation':operation,'signing_test_attempt_id':str(attempt.id),'package_digest':package.digest,
             'envelope_id':attempt.envelope_id,'approval_id':str(decision.id) if decision else '',
             'policy_digest':canonical_hash(policy()) if operation==OP_SEND else ''}
    result=docusign.begin(actor,session_key,context)
    state=parse_qs(urlsplit(result['authorization_url']).query)['state'][0]
    attempt.challenge=docusign.DocusignChallenge.objects.get(state_digest=docusign.digest(state))
    if operation==OP_READ:attempt.state='READ_PENDING'
    attempt.save(update_fields=['challenge','state'])
    audit(actor,'signing_test.authorization_started',package.source.plan.msr.project_id,
          {'attempt_id':str(attempt.id),'operation':operation,'challenge_id':str(attempt.challenge_id)})
    return result


@sensitive_variables()
def provider(account_id,envelope_id,token,payload=None,resource=''):
    development()
    account=str(UUID(account_id));eid=str(UUID(envelope_id)) if envelope_id else ''
    if payload is not None:
        if eid or payload.get('status')!='sent' or not str(payload.get('emailSubject','')).startswith('GECC SANDBOX SIGNING TEST'):
            raise ValidationError('Only approved sandbox signing-test creation is supported.')
        path=f'/restapi/v2.1/accounts/{account}/envelopes'
    else:
        if not eid or resource not in {'','/recipients?include_tabs=true','/documents'}:raise ValidationError('Unsupported signing-test read.')
        path=f'/restapi/v2.1/accounts/{account}/envelopes/{eid}{resource}'
    request=Request(docusign.BASE_URI+path,data=None if payload is None else json.dumps(payload).encode(),
                    headers={'Authorization':'Bearer '+token,'Accept':'application/json','Content-Type':'application/json'})
    try:
        with build_opener(docusign.NoRedirects()).open(request,timeout=12) as response:
            raw=response.read(1048577)
            if len(raw)>1048576:raise ValueError()
            result=json.loads(raw)
            if not isinstance(result,dict):raise ValueError()
            return result
    except Exception:raise ValidationError('Signing-test provider operation did not complete. No automatic send retry is permitted.') from None


@sensitive_variables()
def pdf_document(account_id,envelope_id,document_id,token):
    development()
    if document_id not in {'1','2','certificate'}:raise ValidationError('Unsupported signing-test document ID.')
    path=f'/restapi/v2.1/accounts/{UUID(account_id)}/envelopes/{UUID(envelope_id)}/documents/{document_id}'
    request=Request(docusign.BASE_URI+path,headers={'Authorization':'Bearer '+token,'Accept':'application/pdf'})
    try:
        with build_opener(docusign.NoRedirects()).open(request,timeout=15) as response:
            content=response.read(sandbox.MAX_PDF_BYTES+1)
        if len(content)>sandbox.MAX_PDF_BYTES or not content.startswith(b'%PDF-'):raise ValueError()
        reader=PdfReader(BytesIO(content))
        if reader.is_encrypted or not 1<=len(reader.pages)<=150:raise ValueError()
        return content
    except Exception:raise ValidationError('Completed signing-test PDF retrieval failed; retained records were not replaced.') from None


def metadata(package,eid,summary,recipients,documents):
    status=summary.get('status')
    if summary.get('envelopeId')!=eid or status not in STATUSES:raise ValidationError('Unexpected signing-test envelope status or identity.')
    # Reuse strict identity/routing/tab/document checks while accepting sent lifecycle statuses.
    sandbox.validated_evidence(package.payload['envelope_preview'],{**summary,'status':'created'},recipients,documents,eid)
    return status


def stamp(value):
    try:parsed=parse_datetime(value) if isinstance(value,str) and len(value)<100 else None
    except ValueError:parsed=None
    if not parsed or timezone.is_naive(parsed) or parsed>timezone.now():raise ValidationError('Provider completion evidence has an invalid timestamp.')
    return parsed.isoformat()


def retained_bytes(attempt,package,token):
    existing=list(attempt.retained_documents.order_by('document_id'))
    if existing:
        expected={str(i) for i in range(1,len(package.payload['documents'])+1)}|{'certificate'}
        if {d.document_id for d in existing}!=expected:raise ValidationError('Retained signing-test bundle is incomplete.')
        for d in existing:
            if hashlib.sha256(bytes(d.content)).hexdigest()!=d.pdf_sha256:raise ValidationError('Retained signing-test PDF integrity failed.')
        return [], [{'document_id':d.document_id,'pdf_sha256':d.pdf_sha256} for d in existing]
    rows=[];total=0
    for i,d in enumerate(package.payload['documents'],1):
        content=pdf_document(attempt.account_id,attempt.envelope_id,str(i),token);total+=len(content)
        rows.append({'document_id':str(i),'kind':d['kind'],'filename':d['filename'].replace('-SIGNING-TEST.pdf','-SIGNED-SANDBOX.pdf'),
                     'content':content,'pdf_sha256':hashlib.sha256(content).hexdigest()})
    content=pdf_document(attempt.account_id,attempt.envelope_id,'certificate',token);total+=len(content)
    if total>MAX_RETAINED_BYTES:raise ValidationError('Retained signing-test bundle exceeds its size limit.')
    rows.append({'document_id':'certificate','kind':'DOCUSIGN_CERTIFICATE','filename':f'{attempt.envelope_id}-SANDBOX-CERTIFICATE.pdf',
                 'content':content,'pdf_sha256':hashlib.sha256(content).hexdigest()})
    return rows,[{'document_id':d['document_id'],'pdf_sha256':d['pdf_sha256']} for d in rows]


@sensitive_variables()
def finish(actor,challenge,config,token):
    reference=SigningTestAttempt.objects.select_related('package__source__plan__msr').get(pk=challenge.context['signing_test_attempt_id'])
    send=challenge.context['operation']==OP_SEND
    with transaction.atomic():
        Project.objects.select_for_update().get(pk=reference.package.source.plan.msr.project_id)
        attempt=SigningTestAttempt.objects.select_for_update().select_related('package__source__plan__msr__project').get(pk=reference.id)
        package=attempt.package;docusign.authorize(User.objects.get(pk=actor.id));development()
        if (docusign.configuration_digest(docusign.configuration())!=challenge.configuration_digest
                or attempt.challenge_id!=challenge.id or challenge.actor_id!=actor.id or attempt.account_id!=config['account_id']
                or challenge.context['package_digest']!=package.digest or challenge.context['envelope_id']!=attempt.envelope_id):
            raise ValidationError('Signing-test authorization is stale or already used.')
        if send:
            sending_enabled()
            require_no_other_send(package)
            decision=approval_for(package)
            if (attempt.state!='AUTH_PENDING' or attempt.first_send_started_at or str(decision.id)!=challenge.context['approval_id']
                    or canonical_hash(policy())!=challenge.context['policy_digest']):raise ValidationError('Signing-test send approval or email policy changed.')
            payload=copy.deepcopy(package.payload['envelope_preview']);payload['status']='sent'
            payload['emailSubject']='GECC SANDBOX SIGNING TEST - fictional project only'
            payload['emailBlurb']='This is a fictional GECC software test. Sign only for testing. No actual work completion, contract, payment or lender authorization is established.'
            payload['transactionId']=str(attempt.id)
            for doc,entry in zip(payload['documents'],package.payload['documents']):doc['documentBase64']=entry['documentBase64']
            attempt.state='NETWORK_STARTED';attempt.first_send_started_at=timezone.now()
            attempt.save(update_fields=['state','first_send_started_at'])
            audit(actor,'signing_test.send_started',package.source.plan.msr.project_id,{'attempt_id':str(attempt.id),'package_digest':package.digest})
        else:validate(package,current=False)
    # Commit the one-time send intent before any network request; uncertainty never resends.
    if send:
        try:
            response=provider(attempt.account_id,'',token,payload=payload);eid=str(UUID(response.get('envelopeId','')))
            with transaction.atomic():
                item=SigningTestAttempt.objects.select_for_update().get(pk=attempt.id)
                item.envelope_id=eid;item.state='SENT_UNCHECKED';item.save(update_fields=['envelope_id','state'])
                audit(actor,'signing_test.envelope_created',package.source.plan.msr.project_id,{'attempt_id':str(item.id),'envelope_id':eid})
            attempt.envelope_id=eid
        except Exception:
            with transaction.atomic():
                item=SigningTestAttempt.objects.select_for_update().get(pk=attempt.id);item.state='SEND_UNCERTAIN';item.save(update_fields=['state'])
                audit(actor,'signing_test.send_uncertain',package.source.plan.msr.project_id,{'attempt_id':str(item.id),'envelope_id':item.envelope_id})
            raise ValidationError('The sandbox send result is uncertain. Do not send again or create a replacement; inspect this attempt first.') from None
    evidence={'purpose':'FICTIONAL_SANDBOX_SIGNING_TEST','account_id':attempt.account_id,'envelope_id':attempt.envelope_id,
              'package_digest':package.digest,'tokens_retained':False,'send_available':False,'observed_at':timezone.now().isoformat()}
    rows=[];outcome='READ_FAILED';blockers=[]
    try:
        summary=provider(attempt.account_id,attempt.envelope_id,token)
        recipients=provider(attempt.account_id,attempt.envelope_id,token,resource='/recipients?include_tabs=true')
        documents=provider(attempt.account_id,attempt.envelope_id,token,resource='/documents')
        status=metadata(package,attempt.envelope_id,summary,recipients,documents)
        evidence['provider_status']=status;outcome=status.upper()
        if status=='completed':
            evidence['completed_at']=stamp(summary.get('completedDateTime'))
            evidence['signers']=[{'recipient_id':s['recipientId'],'signed_at':stamp(s.get('signedDateTime'))} for s in recipients['signers'] if s.get('status')=='completed']
            if len(evidence['signers'])!=2:raise ValidationError('Both expected recipients must have completed signing.')
            if any(parse_datetime(s['signed_at'])>parse_datetime(evidence['completed_at']) for s in evidence['signers']):
                raise ValidationError('Recipient signing timestamps are later than envelope completion.')
            rows,hashes=retained_bytes(attempt,package,token);evidence['retained_hashes']=hashes;outcome='COMPLETED_RETAINED'
        after=provider(attempt.account_id,attempt.envelope_id,token)
        if any(after.get(k)!=summary.get(k) for k in ['envelopeId','status','lastModifiedDateTime','completedDateTime']):
            raise ValidationError('The envelope changed during inspection; start a fresh read.')
    except Exception:
        rows=[];outcome='READ_FAILED';evidence.pop('retained_hashes',None)
        blockers=['Provider status, recipients, fields or completion evidence could not be verified. Run another read-only check; do not resend.']
    with transaction.atomic():
        Project.objects.select_for_update().get(pk=package.source.plan.msr.project_id)
        item=SigningTestAttempt.objects.select_for_update().select_related('package__source__plan__msr__project').get(pk=attempt.id)
        if item.challenge_id!=challenge.id:
            outcome='SUPERSEDED';rows=[];evidence.pop('retained_hashes',None);blockers.append('A newer read was authorized; this result does not change the attempt state.')
        else:
            fresh_actor=User.objects.get(pk=actor.id)
            if (not fresh_actor.is_active or fresh_actor.role!='COMPTROLLER' or not settings.DEBUG
                    or docusign.configuration_digest(docusign.configuration())!=challenge.configuration_digest):
                outcome='READ_FAILED';rows=[];evidence.pop('retained_hashes',None);blockers.append('Authorization or sandbox configuration changed during inspection.')
            item.state=outcome if outcome!='READ_FAILED' else 'READ_REQUIRED';item.save(update_fields=['state'])
        evidence['outcome']=outcome;evidence['blockers']=blockers;evidence['local_review_blockers']=eligibility(item.package)
        observation=SigningTestObservation.objects.create(attempt=item,challenge=challenge,created_by=actor,evidence=evidence,digest=canonical_hash(evidence))
        for row in rows:SigningTestDocument.objects.create(attempt=item,observation=observation,**row)
        audit(actor,'signing_test.status_recorded',package.source.plan.msr.project_id,{'attempt_id':str(item.id),'observation_id':str(observation.id),'digest':observation.digest,'evidence':evidence})
    return {'status':'SANDBOX_SIGNING_'+outcome,'envelope_id':item.envelope_id,'blockers':blockers,
            'message':'Sandbox signing-test evidence recorded. Return to GECC and refresh the signing-test status. No tokens retained. Production sending remains disabled.'}


def describe(package):
    decision=package.decisions.order_by('-created_at','-id').first();blockers=eligibility(package)
    attempt=SigningTestAttempt.objects.filter(package=package).first()
    config=docusign.configuration()
    try:
        validate(package)
        review_state='REVIEW_REQUIRED' if not decision else 'REVOKED' if decision.decision=='REVOKED' else 'APPROVED' if not blockers else 'BLOCKED'
    except (ValidationError,PermissionDenied):review_state='BLOCKED'
    return {'id':str(package.id),'created_at':package.created_at.isoformat(),'created_by':str(package.created_by_id),
            'customer':package.payload['review']['customer'],'gecc':package.payload['review']['gecc'],
            'test_note':package.payload['test_note'],'status':review_state,
            'blockers':blockers,'configuration_blockers':config['blockers']+([] if os.getenv('GECC_SANDBOX_SIGNING_SEND_ENABLED')=='1' else ['Sandbox signing-test sending is disabled on the backend.']),
            'send_available':not blockers and not config['blockers'] and (not attempt or attempt.state=='AUTH_PENDING') and settings.DEBUG and os.getenv('GECC_SANDBOX_SIGNING_SEND_ENABLED')=='1',
            'decisions':[{'decision':d.decision,'note':d.note,'created_at':d.created_at.isoformat()} for d in package.decisions.order_by('-created_at','-id')],
            'documents':[{'kind':d['kind'],'download_url':f'/api/signing-tests/{package.id}/documents/{i}/'} for i,d in enumerate(package.payload['documents'])],
            'attempt':None if not attempt else {'state':attempt.state,'envelope_id':attempt.envelope_id,
                'first_send_started_at':attempt.first_send_started_at.isoformat() if attempt.first_send_started_at else None,
                'observations':[{'id':str(o.id),'evidence':o.evidence} for o in attempt.observations.order_by('-challenge__created_at','-challenge_id')],
                'retained_documents':[{'kind':d.kind,'pdf_sha256':d.pdf_sha256,'download_url':f'/api/signing-test-documents/{d.id}/'} for d in attempt.retained_documents.order_by('document_id')]}}
