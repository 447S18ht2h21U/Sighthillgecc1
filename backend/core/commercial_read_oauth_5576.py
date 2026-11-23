"""Authenticated read-only commercial sandbox evidence reconciliation.

Never creates, sends, resends, or voids a DocuSign envelope.
Sandbox evidence never establishes an operational customer signature.
"""

import secrets
from datetime import timedelta
from urllib.parse import urlencode
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import docusign, release
from .commercial_send_callback_5573 import verify_identity
from .commercial_reconciliation_5575 import (
    inspect_provider,
    retain_observation,
)
from .models import (
    CommercialSigningAttempt,
    DocusignChallenge,
    Project,
    Role,
)
from .services import audit


OPERATION = 'COMMERCIAL_SANDBOX_READ'


def authorized_reader(actor, project):
    if not actor or not actor.is_active:
        raise PermissionDenied('An active GECC user is required.')
    if actor.role in {Role.COMPTROLLER, Role.CEO}:
        return
    if (
        actor.role == Role.SALES_MANAGER
        and project.reviewer_id == actor.id
    ):
        return
    raise PermissionDenied(
        'Commercial signing verification requires an authorized project reviewer.'
    )


def is_commercial_read_state(state):
    if not isinstance(state, str) or not 32 <= len(state) <= 128:
        return False
    return DocusignChallenge.objects.filter(
        state_digest=docusign.digest(state),
        context__operation=OPERATION,
    ).exists()


@transaction.atomic
def begin_read(actor, session_key, attempt_id):
    if not session_key:
        raise ValidationError('A signed-in GECC session is required.')

    config = docusign.configuration()
    if config['blockers']:
        raise ValidationError({'configuration': config['blockers']})

    try:
        attempt_id = UUID(str(attempt_id))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError('Invalid commercial attempt identifier.') from None

    reference = CommercialSigningAttempt.objects.select_related(
        'package__plan__msr__project'
    ).get(pk=attempt_id)
    project = reference.package.plan.msr.project

    authorized_reader(actor, project)
    Project.objects.select_for_update().get(pk=project.pk)

    attempt = CommercialSigningAttempt.objects.select_for_update().select_related(
        'package__plan__msr__project'
    ).get(pk=attempt_id)

    if (
        not attempt.envelope_id
        or not attempt.first_send_started_at
        or attempt.account_id != config['account_id']
        or attempt.package_digest != attempt.package.digest
    ):
        raise ValidationError(
            'No account-matched, known commercial envelope is available to read. '
            'An uncertain send must be investigated without resending.'
        )

    release.validate_package(attempt.package, check_current=False)

    context = {
        'operation': OPERATION,
        'commercial_attempt_id': str(attempt.pk),
        'package_digest': attempt.package_digest,
        'account_id': attempt.account_id,
        'envelope_id': attempt.envelope_id,
    }

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
        'commercial_signing.read_authorization_started',
        project.pk,
        {'attempt_id': str(attempt.pk), 'challenge_id': str(challenge.pk)},
    )

    url = docusign.AUTH_ORIGIN + '/oauth/auth?' + urlencode({
        'response_type': 'code',
        'scope': 'signature',
        'client_id': config['client_id'],
        'redirect_uri': config['redirect_uri'],
        'state': state,
    })

    return {
        'authorization_url': url,
        'expires_at': challenge.expires_at.isoformat(),
        'environment': 'SANDBOX',
        'operation': 'READ_ONLY',
        'envelope_sent': False,
    }


@transaction.atomic
def consume_read(actor, session_key, state):
    if not is_commercial_read_state(state) or not session_key:
        raise ValidationError('Invalid commercial read authorization state.')

    challenge = DocusignChallenge.objects.select_for_update().get(
        state_digest=docusign.digest(state)
    )
    config = docusign.configuration()

    if (
        challenge.consumed_at is not None
        or challenge.expires_at <= timezone.now()
        or challenge.actor_id != actor.id
        or challenge.session_digest != docusign.digest(session_key)
        or challenge.configuration_digest != docusign.configuration_digest(config)
        or config['blockers']
    ):
        raise ValidationError('Commercial read authorization expired or changed.')

    context = challenge.context
    try:
        attempt_id = UUID(context['commercial_attempt_id'])
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValidationError('Invalid commercial read attempt binding.') from None

    reference = CommercialSigningAttempt.objects.select_related(
        'package__plan__msr__project'
    ).get(pk=attempt_id)
    project = reference.package.plan.msr.project

    authorized_reader(actor, project)
    Project.objects.select_for_update().get(pk=project.pk)

    attempt = CommercialSigningAttempt.objects.select_for_update().select_related(
        'package__plan__msr__project'
    ).get(pk=attempt_id)

    if (
        context.get('operation') != OPERATION
        or context.get('package_digest') != attempt.package_digest
        or context.get('account_id') != attempt.account_id
        or context.get('envelope_id') != attempt.envelope_id
        or attempt.package_digest != attempt.package.digest
        or attempt.account_id != config['account_id']
        or not attempt.first_send_started_at
        or not attempt.envelope_id
    ):
        raise ValidationError('Commercial read binding changed.')

    release.validate_package(attempt.package, check_current=False)

    challenge.consumed_at = timezone.now()
    challenge.save(update_fields=['consumed_at'])

    return challenge, config, attempt


def finish(*, actor, session_key, state, code, error=None):
    challenge, config, attempt = consume_read(
        actor, session_key, state
    )

    if error or not isinstance(code, str) or not code or len(code) > 16384:
        raise ValidationError(
            'Commercial read authorization declined or incomplete. No send occurred.'
        )

    token, subject = verify_identity(config, code)

    # Provider access below is read-only. There is no envelope creation path.
    evidence, rows = inspect_provider(
        attempt, attempt.package, token
    )

    # Do not persist access tokens, authorization codes, or refresh tokens.
    del token, code

    observation = retain_observation(
        actor, challenge, attempt.pk, evidence, rows
    )

    return {
        'status': 'COMMERCIAL_SANDBOX_READ_RECORDED',
        'attempt_id': str(attempt.pk),
        'observation_id': str(observation.pk),
        'provider_status': evidence['provider_status'],
        'sandbox': True,
        'documents_retained': len(rows) == 3,
        'operational_signature_authorized': False,
        'installation_authorized': False,
        'envelope_sent': False,
        'message': (
            'Commercial sandbox evidence inspected. Return to GECC '
            'and refresh the existing signing transaction. '
            'No envelope sent and no tokens retained.'
        ),
    }


def private(response):
    response['Cache-Control'] = 'private, no-store'
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def connect_read(request, attempt_id):
    if not isinstance(request.data, dict) or request.data.get('confirmed') is not True:
        raise ValidationError(
            'Explicitly confirm a read-only check of the existing commercial envelope.'
        )

    result = begin_read(
        request.user,
        request.session.session_key,
        attempt_id,
    )
    return private(Response(result))
