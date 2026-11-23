"""Controlled commercial signing transaction authorization.

No DocuSign provider calls, sending, or signature assertions occur here.
Sandbox signing-test evidence is not operational commercial evidence.
"""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import release, sandbox
from .documents import canonical_hash
from .models import (
    CommercialSigningAttempt,
    Project,
    ReleasePackage,
    Role,
)


def authorize_sender(actor, project):
    """Enforce the business-specific commercial sending permission."""
    if not actor or not actor.is_active:
        raise PermissionDenied('An active commercial sender is required.')

    if actor.role == Role.CEO:
        return

    if (
        actor.role == Role.SALES_MANAGER
        and project.reviewer_id == actor.id
    ):
        return

    raise PermissionDenied(
        'Only the assigned Sales Manager or CEO may authorize commercial sending.'
    )


def approved_source(package):
    """Validate exact reviewed documents and current independent approval."""
    package = ReleasePackage.objects.select_related(
        'plan__msr__project',
        'created_by',
    ).get(pk=package.pk)

    if package.plan.group != 'COMMERCIAL':
        raise ValidationError('A commercial signing package is required.')

    if package.payload.get('purpose') != 'FICTIONAL_PRE_SIGN_COMMERCIAL':
        raise ValidationError('Unexpected release package purpose.')

    sandbox.current(package.plan)
    release.validate_package(package)

    if release.status(package)['status'] != 'APPROVED':
        raise ValidationError(
            'Current independent commercial release approval is required.'
        )

    decision = package.decisions.order_by('-created_at', '-id').first()
    if not decision or decision.decision != 'APPROVED':
        raise ValidationError('Commercial release approval is missing.')

    if decision.created_by_id == package.created_by_id:
        raise ValidationError(
            'The release preparer cannot independently approve the package.'
        )

    if canonical_hash({
        'package_digest': package.digest,
        'actor': str(decision.created_by_id),
        'decision': decision.decision,
        'note': decision.note,
    }) != decision.digest:
        raise ValidationError('Release approval integrity verification failed.')

    documents = package.payload.get('documents')
    if (
        not isinstance(documents, list)
        or len(documents) != 2
        or {entry.get('kind') for entry in documents} != {'CONTRACT', 'INVOICE'}
    ):
        raise ValidationError(
            'The approved commercial release must contain exactly '
            'the Contract and Invoice.'
        )

    return package, decision


def existing_send_blockers(project_id):
    """Do not replace active, completed, or uncertain commercial transactions."""
    return CommercialSigningAttempt.objects.filter(
        package__plan__msr__project_id=project_id,
        first_send_started_at__isnull=False,
    ).exists()


@transaction.atomic
def reserve_attempt(actor, package_id, account_id):
    """Reserve a commercial attempt; this function cannot transmit it."""
    reference = ReleasePackage.objects.select_related(
        'plan__msr__project'
    ).get(pk=package_id)

    Project.objects.select_for_update().get(
        pk=reference.plan.msr.project_id
    )

    package, approval = approved_source(reference)
    authorize_sender(actor, package.plan.msr.project)

    if existing_send_blockers(package.plan.msr.project_id):
        raise ValidationError(
            'An earlier commercial signing transaction was started. '
            'Inspect its status; do not initiate another envelope.'
        )

    account_id = str(account_id).strip()
    from uuid import UUID
    try:
        account_id = str(UUID(account_id))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError(
            'A valid DocuSign account identifier is required.'
        ) from None

    existing = CommercialSigningAttempt.objects.filter(
        package=package
    ).first()

    if existing:
        if (
            existing.account_id != account_id
            or existing.package_digest != package.digest
            or existing.actor_id != actor.id
            or existing.state != 'AUTH_PENDING'
            or existing.first_send_started_at is not None
        ):
            raise ValidationError(
                'The existing commercial attempt cannot be replaced.'
            )
        return existing, False

    attempt = CommercialSigningAttempt.objects.create(
        package=package,
        actor=actor,
        account_id=account_id,
        package_digest=package.digest,
        state='AUTH_PENDING',
    )

    return attempt, True


def commercial_sandbox_enabled():
    """Commercial sandbox work is never enabled implicitly."""
    import os
    from django.conf import settings

    if settings.ENVIRONMENT != 'development' or not settings.DEBUG:
        raise ValidationError(
            'Commercial sandbox signing is unavailable outside development.'
        )

    if os.getenv('GECC_COMMERCIAL_SANDBOX_SEND_ENABLED') != '1':
        raise ValidationError(
            'Commercial sandbox sending is disabled. '
            'Explicit backend activation is required.'
        )


@transaction.atomic
def begin_authorization(
    actor,
    session_key,
    package_id,
    *,
    fictional_project_confirmed=False,
    controlled_recipients_confirmed=False,
):
    """Authorize a commercial sandbox transaction without sending it.

    A later callback must independently revalidate authorization,
    package approval, account binding, and send uniqueness.
    """
    from urllib.parse import parse_qs, urlsplit
    from . import docusign
    from .models import DocusignChallenge

    commercial_sandbox_enabled()

    if fictional_project_confirmed is not True:
        raise ValidationError(
            'Confirm that this is a fictional acceptance project.'
        )

    if controlled_recipients_confirmed is not True:
        raise ValidationError(
            'Confirm that all DocuSign recipients are controlled test accounts.'
        )

    if not session_key:
        raise ValidationError(
            'An authenticated GECC session is required.'
        )

    config = docusign.configuration()

    if config['blockers']:
        raise ValidationError({
            'configuration': config['blockers']
        })

    reference = ReleasePackage.objects.select_related(
        'plan__msr__project'
    ).get(pk=package_id)

    Project.objects.select_for_update().get(
        pk=reference.plan.msr.project_id
    )

    package, approval = approved_source(reference)
    authorize_sender(actor, package.plan.msr.project)
    controlled_commercial_recipients(package.plan.review)

    if existing_send_blockers(package.plan.msr.project_id):
        raise ValidationError(
            'A commercial send already started for this project. '
            'Inspect its existing attempt; never automatically resend.'
        )

    attempt, created = reserve_attempt(
        actor,
        package.id,
        config['account_id'],
    )

    if attempt.challenge_id:
        raise ValidationError(
            'A commercial authorization challenge already exists. '
            'Inspect it before creating another.'
        )

    context = {
        'operation': 'COMMERCIAL_SANDBOX_SEND',
        'commercial_attempt_id': str(attempt.id),
        'package_digest': package.digest,
        'approval_id': str(approval.id),
        'account_id': attempt.account_id,
        'fictional_project': True,
    }

    result = begin_commercial_oauth(actor, session_key, context)

    state = parse_qs(
        urlsplit(result['authorization_url']).query
    ).get('state', [])

    if len(state) != 1:
        raise ValidationError(
            'DocuSign authorization challenge could not be bound.'
        )

    challenge = DocusignChallenge.objects.get(
        state_digest=docusign.digest(state[0])
    )

    attempt.challenge = challenge
    attempt.save(update_fields=['challenge'])

    return {
        'authorization_url': result['authorization_url'],
        'expires_at': result['expires_at'],
        'environment': 'SANDBOX',
        'attempt_id': str(attempt.id),
        'envelope_sent': False,
    }


def controlled_commercial_recipients(review):
    """Require exact reviewed recipients to match a backend test allowlist."""
    import os
    from .signing_test import address

    raw = os.getenv('GECC_COMMERCIAL_SANDBOX_TEST_EMAILS', '')

    if not raw or len(raw) > 2000:
        raise ValidationError(
            'Configure controlled commercial sandbox email accounts.'
        )

    entries = raw.split(',')

    if not 2 <= len(entries) <= 10:
        raise ValidationError(
            'Configure two to ten controlled sandbox email accounts.'
        )

    allowed = [address(value) for value in entries]

    if len(set(allowed)) != len(allowed):
        raise ValidationError(
            'Commercial sandbox email allowlist contains duplicates.'
        )

    if not isinstance(review, dict):
        raise ValidationError('Invalid reviewed recipient configuration.')

    customer = review.get('customer')
    gecc = review.get('gecc')

    if not isinstance(customer, dict) or not isinstance(gecc, dict):
        raise ValidationError('Both signing recipients must be reviewed.')

    recipients = (
        address(customer.get('email')),
        address(gecc.get('email')),
    )

    if recipients[0] == recipients[1]:
        raise ValidationError(
            'Customer and GECC signing accounts must be distinct.'
        )

    if not set(recipients).issubset(set(allowed)):
        raise ValidationError(
            'Reviewed recipients do not match approved controlled '
            'commercial sandbox email accounts.'
        )

    return recipients


def begin_commercial_oauth(actor, session_key, context):
    """Create a commercial-only OAuth challenge without changing sandbox roles."""
    import secrets
    from datetime import timedelta
    from urllib.parse import urlencode
    from django.utils import timezone
    from . import docusign
    from .models import DocusignChallenge
    from .services import audit

    if not session_key:
        raise ValidationError(
            'An authenticated GECC session is required.'
        )

    if (
        not isinstance(context, dict)
        or context.get('operation') != 'COMMERCIAL_SANDBOX_SEND'
        or context.get('fictional_project') is not True
        or not context.get('commercial_attempt_id')
    ):
        raise ValidationError(
            'An authorized commercial signing context is required.'
        )

    config = docusign.configuration()

    if config['blockers']:
        raise ValidationError({
            'configuration': config['blockers']
        })

    if context.get('account_id') != config['account_id']:
        raise ValidationError(
            'Commercial signing account configuration changed.'
        )

    state = secrets.token_urlsafe(32)

    challenge = DocusignChallenge.objects.create(
        actor=actor,
        state_digest=docusign.digest(state),
        session_digest=docusign.digest(session_key),
        configuration_digest=docusign.configuration_digest(config),
        expires_at=timezone.now() + timedelta(minutes=10),
        context=context,
    )

    audit(
        actor,
        'commercial_signing.authorization_started',
        actor.id,
        {
            'challenge_id': str(challenge.id),
            'environment': 'SANDBOX',
            'commercial_attempt_id': context['commercial_attempt_id'],
        },
    )

    authorization_url = (
        docusign.AUTH_ORIGIN
        + '/oauth/auth?'
        + urlencode({
            'response_type': 'code',
            'scope': 'signature',
            'client_id': config['client_id'],
            'redirect_uri': config['redirect_uri'],
            'state': state,
        })
    )

    return {
        'authorization_url': authorization_url,
        'expires_at': challenge.expires_at.isoformat(),
        'environment': 'SANDBOX',
    }
