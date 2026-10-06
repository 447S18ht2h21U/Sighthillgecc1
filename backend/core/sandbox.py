"""Test-only package and unsent sandbox draft. No send/update endpoint exists."""
import base64
import copy
import hashlib
import json
from urllib.request import Request, build_opener
from uuid import UUID
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from rest_framework.exceptions import ValidationError
from . import docusign, signing
from .documents import canonical_hash, render_pdf
from .models import Document, Project, SandboxAttempt, SandboxPackage, SigningPlan
from .services import authorize, audit

PACKAGE_VERSION = 'sandbox-0.1'
MAX_PDF_BYTES = 8 * 1024 * 1024


def current(plan):
    if not settings.DEBUG:
        raise ValidationError('Sandbox packages are available only in local development.')
    if signing.status(plan)['status'] != 'PREPARED':
        raise ValidationError('The recipient review is stale, cancelled, changed, or invalid. Prepare a current review.')
    review = plan.review
    if plan.msr.status != 'APPROVED' or not signing.candidates(plan.msr.project, plan.group).filter(pk=review['gecc']['user_id']).exists():
        raise ValidationError('The reviewed GECC signer is no longer eligible for this project.')
    if review['snapshot_sha256'] != canonical_hash(plan.msr.snapshot):
        raise ValidationError('Approved snapshot integrity verification failed.')
    for source in review['documents']:
        document = Document.objects.filter(pk=source['id'], msr=plan.msr, kind=source['kind']).first()
        if (not document or hashlib.sha256(bytes(document.content)).hexdigest() != source['pdf_sha256']
                or document.pdf_sha256 != source['pdf_sha256'] or document.template_sha256 != source['template_sha256']):
            raise ValidationError('Reviewed source document integrity verification failed.')
    return review


@transaction.atomic
def prepare_package(actor, plan_id):
    plan = SigningPlan.objects.select_related('msr__project').get(pk=plan_id)
    Project.objects.select_for_update().get(pk=plan.msr.project_id)
    # Reload after the project lock: approval/revision/cancellation changes cannot race this read.
    plan = SigningPlan.objects.select_related('msr__project').get(pk=plan_id)
    authorize(actor, plan.msr.project, approval=True)
    review = current(plan)
    existing = SandboxPackage.objects.filter(plan=plan).first()
    if existing:
        validate_package(existing)
        return existing, False
    docs, entries, total = [], [], 0
    for source in review['documents']:
        content, values, template_digest = render_pdf(source['kind'], plan.msr, timezone.now(), sandbox_review=review)
        if template_digest != source['template_sha256']:
            raise ValidationError('The template changed since recipient review. Prepare a new review.')
        total += len(content)
        if total > MAX_PDF_BYTES:
            raise ValidationError('Sandbox package exceeds the local test size limit.')
        filename = f'{plan.msr.project.code}-V{plan.msr.number}-{source["kind"]}-SANDBOX.pdf'
        entries.append({'kind': source['kind'], 'filename': filename, 'pdf_sha256': hashlib.sha256(content).hexdigest(),
                        'template_sha256': template_digest, 'values': values,
                        'documentBase64': base64.b64encode(content).decode()})
        # Only exact package bytes determine provider tab positions.
        from types import SimpleNamespace
        docs.append(SimpleNamespace(content=content, filename=filename))
    payload = {'version': PACKAGE_VERSION, 'purpose': 'SANDBOX_DRAFT_ONLY', 'plan_digest': plan.digest,
               'snapshot_sha256': review['snapshot_sha256'], 'documents': entries,
               'envelope_preview': signing.envelope_preview(docs, review['customer'], review['gecc'], plan.group == 'COMMERCIAL')}
    package = SandboxPackage.objects.create(plan=plan, created_by=actor, payload=payload, digest=canonical_hash(payload))
    audit(actor, 'sandbox.package_prepared', plan.msr.project_id, {'package_id': str(package.id), 'plan_id': str(plan.id),
          'digest': package.digest, 'purpose': payload['purpose'], 'pdf_hashes': [e['pdf_sha256'] for e in entries]})
    return package, True


def validate_package(package, check_current=True):
    if check_current:
        current(package.plan)
    p = package.payload
    if (canonical_hash(p) != package.digest or p['plan_digest'] != package.plan.digest
            or p['snapshot_sha256'] != canonical_hash(package.plan.msr.snapshot)
            or p['purpose'] != 'SANDBOX_DRAFT_ONLY' or p['version'] != PACKAGE_VERSION):
        raise ValidationError('Sandbox package integrity verification failed.')
    for entry in p['documents']:
        content = base64.b64decode(entry['documentBase64'], validate=True)
        if hashlib.sha256(content).hexdigest() != entry['pdf_sha256']:
            raise ValidationError('Sandbox PDF integrity verification failed.')
    if p['envelope_preview']['status'] != 'created':
        raise ValidationError('Only unsent sandbox drafts are permitted.')


def describe(package):
    attempt = SandboxAttempt.objects.filter(package=package).first()
    return {'id': str(package.id), 'plan_id': str(package.plan_id), 'digest': package.digest,
            'purpose': 'SANDBOX_DRAFT_ONLY', 'send_available': False,
            'documents': [{'kind': e['kind'], 'filename': e['filename'], 'pdf_sha256': e['pdf_sha256'],
                           'download_url': f'/api/sandbox-packages/{package.id}/documents/{i}/'} for i,e in enumerate(package.payload['documents'])],
            'attempt': None if not attempt else {'id': str(attempt.id), 'state': attempt.state, 'envelope_id': attempt.envelope_id,
                                                'evidence': attempt.evidence}}


@transaction.atomic
def begin_draft(actor, session_key, package_id, confirmed):
    docusign.authorize(actor)
    if confirmed is not True:
        raise ValidationError('Confirm creation of an unsent sandbox draft.')
    package = SandboxPackage.objects.select_related('plan__msr__project').get(pk=package_id)
    Project.objects.select_for_update().get(pk=package.plan.msr.project_id)
    package = SandboxPackage.objects.select_related('plan__msr__project').get(pk=package_id)
    validate_package(package)
    config = docusign.configuration()
    if config['blockers']:
        raise ValidationError({'configuration': config['blockers']})
    attempt, _ = SandboxAttempt.objects.get_or_create(package=package, defaults={'actor': actor, 'account_id': config['account_id']})
    attempt = SandboxAttempt.objects.select_for_update().get(pk=attempt.id)
    if attempt.state != 'AUTH_PENDING' or attempt.actor_id != actor.id or attempt.account_id != config['account_id']:
        raise ValidationError('This package already has a draft attempt. Inspect its status; do not create a duplicate.')
    result = docusign.begin(actor, session_key, {'sandbox_attempt_id': str(attempt.id), 'package_digest': package.digest})
    # Latest challenge wins, so an older browser tab cannot submit a second draft.
    from urllib.parse import parse_qs, urlsplit
    state = parse_qs(urlsplit(result['authorization_url']).query)['state'][0]
    attempt.challenge = docusign.DocusignChallenge.objects.get(state_digest=docusign.digest(state))
    attempt.save(update_fields=['challenge'])
    audit(actor, 'sandbox.draft_authorized', package.plan.msr.project_id, {'attempt_id': str(attempt.id), 'package_id': str(package.id)})
    return result


@sensitive_variables()
def provider(account_id, envelope_id, token, payload=None, resource=''):
    # Exact sandbox origin, UUID paths, and fixed operations; no sending endpoint.
    account = str(UUID(account_id))
    envelope = str(UUID(envelope_id)) if envelope_id else ''
    if payload is not None:
        if envelope or payload.get('status') != 'created':
            raise ValidationError('Only sandbox draft creation is permitted.')
        path = f'/restapi/v2.1/accounts/{account}/envelopes'
    else:
        if not envelope or resource not in {'', '/recipients?include_tabs=true', '/documents'}:
            raise ValidationError('Unsupported sandbox draft inspection.')
        path = f'/restapi/v2.1/accounts/{account}/envelopes/{envelope}{resource}'
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(docusign.BASE_URI+path, data=data,
                      headers={'Authorization': 'Bearer '+token, 'Accept': 'application/json', 'Content-Type': 'application/json'})
    try:
        with build_opener(docusign.NoRedirects()).open(request, timeout=12) as response:
            raw = response.read(1048577)
            if len(raw)>1048576:
                raise ValueError()
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError()
            return value
    except Exception:
        raise ValidationError('Sandbox provider operation failed. Inspect the existing attempt before trying again.') from None


def validated_evidence(expected, summary, recipients, documents, envelope_id):
    if summary.get('status') != 'created' or summary.get('envelopeId') != envelope_id:
        raise ValidationError('The provider envelope is not the expected unsent draft.')
    actual = recipients.get('signers')
    if not isinstance(actual, list) or len(actual) != 2:
        raise ValidationError('Sandbox draft recipient validation failed.')
    extra = set(recipients) - {'signers', 'currentRoutingOrder', 'recipientCount'}
    if any(isinstance(recipients[k], list) and recipients[k] for k in extra):
        raise ValidationError('Sandbox draft contains unexpected recipients.')
    checks = []
    for signer in expected['recipients']['signers']:
        match = [s for s in actual if s.get('recipientId') == signer['recipientId']]
        if len(match)!=1:
            raise ValidationError('Sandbox draft recipient validation failed.')
        observed = match[0]
        for key in ['name','email','routingOrder']:
            if observed.get(key) != signer[key]:
                raise ValidationError('Sandbox draft signer identity or routing changed.')
        tabs = observed.get('tabs', {})
        if not isinstance(tabs, dict):
            raise ValidationError('Sandbox draft tab validation failed.')
        for tab_type, entries in signer['tabs'].items():
            seen = tabs.get(tab_type, [])
            if not isinstance(seen,list) or len(seen)!=len(entries):
                raise ValidationError('Sandbox draft tab count changed.')
            for entry in entries:
                matches = [t for t in seen if all(str(t.get(k,''))==entry[k] for k in ['documentId','pageNumber','xPosition','yPosition','tabLabel'])]
                if len(matches)!=1:
                    raise ValidationError('Sandbox draft tab placement changed.')
                if entry.get('optional') == 'false' and str(matches[0].get('optional','')).lower() != 'false':
                    raise ValidationError('Sandbox draft signature became optional.')
        if any(isinstance(v,list) and v for k,v in tabs.items() if k not in signer['tabs']):
            raise ValidationError('Sandbox draft contains unexpected tabs.')
        checks.append({'recipient_id': signer['recipientId'], 'routing_order': signer['routingOrder'], 'tabs_verified': True})
    docs = documents.get('envelopeDocuments')
    if not isinstance(docs, list):
        raise ValidationError('Sandbox draft document validation failed.')
    regular = [d for d in docs if d.get('documentId')!='certificate']
    if sorted((d.get('documentId'),d.get('name')) for d in regular)!=sorted((d['documentId'],d['name']) for d in expected['documents']):
        raise ValidationError('Sandbox draft documents changed.')
    return {'provider_status': 'created', 'recipient_checks': checks, 'document_ids_and_names_verified': True,
            'visual_review_required': True, 'send_available': False, 'tokens_retained': False,
            'observed_at': timezone.now().isoformat()}


@sensitive_variables()
def finish_draft(actor, challenge, config, token):
    reference = SandboxAttempt.objects.select_related('package__plan__msr').get(pk=challenge.context['sandbox_attempt_id'])
    with transaction.atomic():
        Project.objects.select_for_update().get(pk=reference.package.plan.msr.project_id)
        attempt = SandboxAttempt.objects.select_for_update().select_related('package__plan__msr__project').get(pk=reference.id)
        package = SandboxPackage.objects.select_related('plan__msr__project').get(pk=attempt.package_id)
        if (attempt.actor_id!=actor.id or attempt.challenge_id!=challenge.id or attempt.state!='AUTH_PENDING'
                or attempt.account_id!=config['account_id'] or challenge.context['package_digest']!=package.digest):
            raise ValidationError('Sandbox draft authorization is stale or already used.')
        validate_package(package)
        payload = copy.deepcopy(package.payload['envelope_preview'])
        payload['emailSubject'] = 'GECC sandbox draft - DO NOT SEND'
        payload['transactionId'] = str(attempt.id)
        for doc, entry in zip(payload['documents'], package.payload['documents']):
            doc['documentBase64'] = entry['documentBase64']
        attempt.state='NETWORK_STARTED'
        attempt.save(update_fields=['state'])
        audit(actor, 'sandbox.draft_create_started', package.plan.msr.project_id, {'attempt_id': str(attempt.id), 'package_digest': package.digest})
    # Commit intent before POST. Never automatically retry an ambiguous create.
    try:
        result = provider(config['account_id'], '', token, payload=payload)
        envelope_id = str(UUID(result.get('envelopeId', '')))
        # Persist the returned ID before inspection so failed reads never lose it.
        with transaction.atomic():
            attempt = SandboxAttempt.objects.select_for_update().get(pk=attempt.id)
            attempt.envelope_id=envelope_id;attempt.state='CREATED_UNVALIDATED'
            attempt.save(update_fields=['envelope_id','state'])
            audit(actor,'sandbox.draft_created',package.plan.msr.project_id,{'attempt_id':str(attempt.id),'envelope_id':envelope_id,'account_id':config['account_id']})
        summary=provider(config['account_id'],envelope_id,token)
        recipients=provider(config['account_id'],envelope_id,token,resource='/recipients?include_tabs=true')
        documents=provider(config['account_id'],envelope_id,token,resource='/documents')
        evidence=validated_evidence(payload,summary,recipients,documents,envelope_id)
        with transaction.atomic():
            Project.objects.select_for_update().get(pk=package.plan.msr.project_id)
            package=SandboxPackage.objects.select_related('plan__msr__project').get(pk=package.id)
            validate_package(package)
            attempt=SandboxAttempt.objects.select_for_update().get(pk=attempt.id)
            attempt.state='DRAFT_VALIDATED';attempt.evidence=evidence;attempt.save(update_fields=['state','evidence'])
            audit(actor,'sandbox.draft_validated',package.plan.msr.project_id,{'attempt_id':str(attempt.id),'envelope_id':envelope_id,'evidence':evidence})
    except Exception:
        # POST may have succeeded despite timeout. This package cannot create another draft.
        with transaction.atomic():
            attempt=SandboxAttempt.objects.select_for_update().get(pk=attempt.id)
            attempt.state='RECONCILIATION_REQUIRED';attempt.save(update_fields=['state'])
            audit(actor,'sandbox.draft_inspection_required',package.plan.msr.project_id,{'attempt_id':str(attempt.id),'envelope_id':attempt.envelope_id})
        raise ValidationError('Sandbox draft requires inspection. Return to GECC; do not create another copy. No send operation was requested.') from None
    return {'status':'SANDBOX_DRAFT_VALIDATED','envelope_id':envelope_id,
            'message':'Unsent sandbox draft checked. No tokens retained. Return to GECC for document and visual review; sending remains disabled.'}
