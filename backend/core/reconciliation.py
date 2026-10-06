"""Read-only, explicitly authorized sandbox draft metadata observations."""
from urllib.parse import parse_qs, urlsplit
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from rest_framework.exceptions import ValidationError
from . import docusign, sandbox
from .documents import canonical_hash
from .models import DocusignChallenge, Project, SandboxAttempt, SandboxObservation
from .services import audit

STATES = {'DRAFT_VALIDATED', 'CREATED_UNVALIDATED', 'RECONCILIATION_REQUIRED', 'RECHECK_PENDING'}


def eligible(actor, attempt, config):
    docusign.authorize(actor)
    if not settings.DEBUG or config['blockers']:
        raise ValidationError('Configure sandbox authorization in local development before checking a draft.')
    if not attempt.envelope_id or attempt.state not in STATES:
        raise ValidationError('No known sandbox envelope is available to check. Do not create a replacement for an ambiguous attempt.')
    if attempt.account_id != config['account_id']:
        raise ValidationError('The draft belongs to a different configured sandbox account.')
    sandbox.validate_package(attempt.package, check_current=False)


@transaction.atomic
def begin(actor, session_key, package_id, confirmed):
    if confirmed is not True:
        raise ValidationError('Confirm a read-only check of the existing sandbox draft.')
    docusign.authorize(actor)
    reference = SandboxAttempt.objects.select_related('package__plan__msr').filter(package_id=package_id).first()
    if not reference:
        raise ValidationError('No sandbox draft attempt exists for this package.')
    Project.objects.select_for_update().get(pk=reference.package.plan.msr.project_id)
    attempt = SandboxAttempt.objects.select_for_update().select_related('package__plan__msr__project').get(pk=reference.id)
    config = docusign.configuration()
    eligible(actor, attempt, config)
    context = {'operation': 'SANDBOX_RECONCILIATION', 'sandbox_attempt_id': str(attempt.id),
               'package_digest': attempt.package.digest, 'envelope_id': attempt.envelope_id}
    result = docusign.begin(actor, session_key, context)
    state = parse_qs(urlsplit(result['authorization_url']).query)['state'][0]
    attempt.challenge = DocusignChallenge.objects.get(state_digest=docusign.digest(state))
    # A pending/failed authorization must not leave the earlier validation appearing current.
    attempt.state = 'RECHECK_PENDING'
    attempt.save(update_fields=['challenge', 'state'])
    audit(actor, 'sandbox.reconciliation_authorized', attempt.package.plan.msr.project_id,
          {'attempt_id': str(attempt.id), 'challenge_id': str(attempt.challenge_id), 'envelope_id': attempt.envelope_id})
    return result


def bound(actor, challenge, attempt, config):
    eligible(actor, attempt, config)
    if (challenge.configuration_digest != docusign.configuration_digest(config)
            or attempt.challenge_id != challenge.id or challenge.actor_id != actor.id
            or challenge.context.get('package_digest') != attempt.package.digest
            or challenge.context.get('envelope_id') != attempt.envelope_id):
        raise ValidationError('Sandbox check authorization is stale. Start a fresh check from GECC.')


def local_blockers(package):
    try:
        sandbox.validate_package(package)
        return []
    except ValidationError:
        return ['The local recipient review or approved project is no longer current or eligible.']


@sensitive_variables()
def finish(actor, challenge, config, token):
    reference = SandboxAttempt.objects.select_related('package__plan__msr').get(pk=challenge.context['sandbox_attempt_id'])
    with transaction.atomic():
        Project.objects.select_for_update().get(pk=reference.package.plan.msr.project_id)
        attempt = SandboxAttempt.objects.select_for_update().select_related('package__plan__msr__project').get(pk=reference.id)
        bound(actor, challenge, attempt, config)
        package = attempt.package
        blockers = local_blockers(package)
    started = timezone.now().isoformat()
    evidence = {'operation': 'SANDBOX_RECONCILIATION', 'package_digest': package.digest,
                'account_id': attempt.account_id, 'envelope_id': attempt.envelope_id,
                'started_at': started, 'metadata_matched': False, 'provider_pdf_bytes_verified': False,
                'visual_review_required': True, 'tokens_retained': False, 'send_available': False}
    outcome = 'READ_FAILED'
    try:
        summary = sandbox.provider(attempt.account_id, attempt.envelope_id, token)
        recipients = sandbox.provider(attempt.account_id, attempt.envelope_id, token, resource='/recipients?include_tabs=true')
        documents = sandbox.provider(attempt.account_id, attempt.envelope_id, token, resource='/documents')
        after = sandbox.provider(attempt.account_id, attempt.envelope_id, token)
        status = summary.get('status')
        evidence['provider_status'] = status if status in {'created','sent','delivered','signed','completed','declined','voided','deleted','correct'} else 'unknown'
        if any(summary.get(key) != after.get(key) for key in ['envelopeId', 'status', 'lastModifiedDateTime']):
            outcome = 'CHANGED'
            blockers.append('The provider envelope changed during inspection. Run a fresh check.')
        else:
            try:
                checks = sandbox.validated_evidence(package.payload['envelope_preview'], summary, recipients, documents, attempt.envelope_id)
                evidence.update(checks)
                evidence['metadata_matched'] = True
                outcome = 'MATCHED' if not blockers else 'BLOCKED'
            except ValidationError:
                outcome = 'CHANGED'
                blockers.append('Provider draft status, recipients, routing, documents or signature fields differ from the saved sandbox package.')
    except Exception:
        blockers.append('Provider inspection did not complete. Start a fresh read-only check; no replacement draft was created.')
    evidence['observed_at'] = timezone.now().isoformat()
    with transaction.atomic():
        Project.objects.select_for_update().get(pk=package.plan.msr.project_id)
        attempt = SandboxAttempt.objects.select_for_update().select_related('package__plan__msr__project').get(pk=attempt.id)
        # Recheck role, config and local eligibility after network I/O; history remains readable.
        if attempt.challenge_id != challenge.id:
            outcome = 'SUPERSEDED'
            blockers.append('A newer sandbox check was authorized. This result does not update the draft state.')
        else:
            try:
                bound(actor, challenge, attempt, docusign.configuration())
            except (ValidationError, docusign.PermissionDenied):
                outcome = 'BLOCKED'
                blockers.append('Authorization, account configuration or package eligibility changed during inspection.')
            blockers.extend(b for b in local_blockers(attempt.package) if b not in blockers)
            if blockers and outcome == 'MATCHED':
                outcome = 'BLOCKED'
            attempt.state = 'DRAFT_VALIDATED' if outcome == 'MATCHED' else 'RECONCILIATION_REQUIRED'
            attempt.save(update_fields=['state'])
        evidence['outcome'] = outcome
        evidence['blockers'] = blockers
        observation = SandboxObservation.objects.create(attempt=attempt, challenge=challenge, created_by=actor,
                                                       evidence=evidence, digest=canonical_hash(evidence))
        audit(actor, 'sandbox.reconciliation_recorded', package.plan.msr.project_id,
              {'observation_id': str(observation.id), 'attempt_id': str(attempt.id), 'digest': observation.digest, 'evidence': evidence})
    return {'status': 'SANDBOX_RECONCILIATION_'+outcome, 'envelope_id': attempt.envelope_id,
            'observation_id': str(observation.id), 'message': 'Existing sandbox draft checked. Return to GECC and refresh sandbox draft status. No tokens retained; sending remains disabled.'}
