"""Controlled fictional commercial DocuSign sending callback.

A send is permitted only after explicit backend activation. The send-start
marker commits before outbound traffic; uncertain sends are never retried.
Sandbox evidence does not establish operational customer signatures.
"""

import base64
import copy
import json
from urllib.request import Request, build_opener
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import docusign
from .commercial_signing_5567 import (
    approved_source,
    authorize_sender,
    commercial_sandbox_enabled,
    controlled_commercial_recipients,
)
from .documents import canonical_hash
from .models import (
    CommercialSigningAttempt,
    DocusignChallenge,
    Project,
    User,
)
from .services import audit


OPERATION = 'COMMERCIAL_SANDBOX_SEND'


def is_commercial_state(state):
    if not isinstance(state, str) or not 32 <= len(state) <= 128:
        return False
    return DocusignChallenge.objects.filter(
        state_digest=docusign.digest(state),
        context__operation=OPERATION,
    ).exists()


@transaction.atomic
def consume_commercial(actor, session_key, state):
    if not is_commercial_state(state) or not session_key:
        raise ValidationError('Invalid commercial authorization state.')

    challenge = DocusignChallenge.objects.select_for_update().get(
        state_digest=docusign.digest(state)
    )
    context = challenge.context
    config = docusign.configuration()

    if (
        challenge.consumed_at is not None
        or challenge.expires_at <= timezone.now()
        or challenge.actor_id != actor.id
        or challenge.session_digest != docusign.digest(session_key)
        or challenge.configuration_digest != docusign.configuration_digest(config)
        or config['blockers']
    ):
        raise ValidationError('Commercial authorization expired or changed.')

    try:
        attempt_id = UUID(context['commercial_attempt_id'])
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValidationError('Commercial attempt binding is invalid.') from None

    reference = CommercialSigningAttempt.objects.select_related(
        'package__plan__msr__project'
    ).get(pk=attempt_id)

    Project.objects.select_for_update().get(
        pk=reference.package.plan.msr.project_id
    )
    attempt = CommercialSigningAttempt.objects.select_for_update().get(
        pk=attempt_id
    )

    package, approval = approved_source(reference.package)
    authorize_sender(actor, package.plan.msr.project)
    controlled_commercial_recipients(package.plan.review)
    commercial_sandbox_enabled()

    if (
        attempt.actor_id != actor.id
        or attempt.challenge_id != challenge.id
        or attempt.package_id != package.id
        or attempt.package_digest != package.digest
        or attempt.account_id != config['account_id']
        or attempt.state != 'AUTH_PENDING'
        or attempt.first_send_started_at is not None
        or context.get('package_digest') != package.digest
        or context.get('approval_id') != str(approval.id)
        or context.get('account_id') != config['account_id']
        or context.get('fictional_project') is not True
    ):
        raise ValidationError('Commercial sending authorization is stale.')

    other = CommercialSigningAttempt.objects.filter(
        package__plan__msr__project_id=package.plan.msr.project_id,
        first_send_started_at__isnull=False,
    ).exclude(pk=attempt.id)

    if other.exists():
        raise ValidationError('A commercial send already started. Do not resend.')

    challenge.consumed_at = timezone.now()
    challenge.save(update_fields=['consumed_at'])
    return challenge, config, attempt


def verify_identity(config, code):
    import base64 as b64

    credentials = (
        config['client_id'] + ':' + config['client_secret']
    ).encode('utf-8')
    basic = b64.b64encode(credentials).decode('ascii')

    tokens = docusign.request_json(
        '/oauth/token',
        'Basic ' + basic,
        {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': config['redirect_uri'],
        },
    )
    token = tokens.get('access_token')
    lifetime = tokens.get('expires_in')

    if (
        not isinstance(token, str)
        or not token
        or len(token) > 16384
        or str(tokens.get('token_type', '')).lower() != 'bearer'
        or type(lifetime) is not int
        or not 0 < lifetime <= 86400
    ):
        raise ValidationError('Invalid commercial OAuth token metadata.')

    info = docusign.request_json('/oauth/userinfo', 'Bearer ' + token)
    accounts = info.get('accounts')
    if not isinstance(accounts, list):
        raise ValidationError('Commercial OAuth account verification failed.')

    matches = [
        row for row in accounts
        if isinstance(row, dict)
        and row.get('account_id') == config['account_id']
        and row.get('base_uri') == docusign.BASE_URI
    ]

    if len(matches) != 1:
        raise ValidationError('Commercial OAuth sandbox account mismatch.')

    try:
        subject = str(UUID(info.get('sub', '')))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError('Commercial OAuth identity invalid.') from None

    return token, subject


def send_once(account_id, token, payload):
    """One outbound request only. No automatic retry, including network failure."""
    path = f'/restapi/v2.1/accounts/{UUID(account_id)}/envelopes'
    request = Request(
        docusign.BASE_URI + path,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': 'Bearer ' + token,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        },
    )

    try:
        with build_opener(docusign.NoRedirects()).open(
            request, timeout=12
        ) as response:
            raw = response.read(1048577)
            if len(raw) > 1048576:
                raise ValueError('Oversized provider response.')
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError('Invalid provider response.')
            return str(UUID(result['envelopeId']))
    except Exception:
        raise ValidationError(
            'Commercial send outcome uncertain. Do not retry or create '
            'another envelope until this attempt is independently reconciled.'
        ) from None


def finish(*, actor, session_key, state, code, error=None):
    """Verify OAuth and send one fictional commercial envelope at most once."""
    challenge, config, attempt = consume_commercial(
        actor, session_key, state
    )

    if (
        error
        or not isinstance(code, str)
        or not code
        or len(code) > 16384
    ):
        raise ValidationError(
            'Commercial OAuth declined or incomplete. No send occurred.'
        )

    token, subject = verify_identity(config, code)

    with transaction.atomic():
        reference = CommercialSigningAttempt.objects.select_related(
            'package__plan__msr__project'
        ).get(pk=attempt.pk)

        Project.objects.select_for_update().get(
            pk=reference.package.plan.msr.project_id
        )
        current = CommercialSigningAttempt.objects.select_for_update().get(
            pk=attempt.pk
        )

        package, approval = approved_source(reference.package)
        authorize_sender(
            User.objects.get(pk=actor.pk),
            package.plan.msr.project,
        )
        controlled_commercial_recipients(package.plan.review)
        commercial_sandbox_enabled()

        if (
            current.challenge_id != challenge.id
            or current.actor_id != actor.pk
            or current.state != 'AUTH_PENDING'
            or current.first_send_started_at is not None
            or current.package_digest != package.digest
            or current.account_id != config['account_id']
            or str(approval.id) != challenge.context['approval_id']
            or docusign.configuration_digest(docusign.configuration())
               != challenge.configuration_digest
        ):
            raise ValidationError('Commercial send authorization changed.')

        if CommercialSigningAttempt.objects.filter(
            package__plan__msr__project_id=package.plan.msr.project_id,
            first_send_started_at__isnull=False,
        ).exclude(pk=current.pk).exists():
            raise ValidationError('Another commercial send already started.')

        payload = build_commercial_payload(package, str(current.id))

        current.first_send_started_at = timezone.now()
        current.state = 'NETWORK_STARTED'
        current.save(update_fields=['first_send_started_at', 'state'])

        audit(
            actor,
            'commercial_signing.send_started',
            package.plan.msr.project_id,
            {
                'attempt_id': str(current.pk),
                'package_digest': package.digest,
                'sandbox_subject': subject,
            },
        )

    # The database transaction has committed before outbound traffic.
    # A failure here must never trigger a second send automatically.
    try:
        envelope_id = send_once(config['account_id'], token, payload)
    except Exception:
        with transaction.atomic():
            item = CommercialSigningAttempt.objects.select_for_update().get(
                pk=attempt.pk
            )
            item.state = 'SEND_UNCERTAIN'
            item.save(update_fields=['state'])
        raise

    with transaction.atomic():
        item = CommercialSigningAttempt.objects.select_for_update().get(
            pk=attempt.pk
        )
        item.envelope_id = envelope_id
        item.state = 'SENT_UNCHECKED'
        item.save(update_fields=['envelope_id', 'state'])

        audit(
            actor,
            'commercial_signing.envelope_created',
            package.plan.msr.project_id,
            {
                'attempt_id': str(item.pk),
                'envelope_id': envelope_id,
                'sandbox': True,
            },
        )

    return {
        'status': 'COMMERCIAL_SANDBOX_SENT_UNCHECKED',
        'attempt_id': str(attempt.pk),
        'envelope_id': envelope_id,
        'sandbox': True,
        'signatures_verified': False,
        'installation_authorized': False,
        'message': (
            'Fictional commercial sandbox envelope sent. '
            'Provider completion and signed documents are not yet verified.'
        ),
    }


def build_commercial_payload(package, attempt_id):
    """Build the envelope from exact approved release PDFs and reviewed signers."""
    import hashlib
    from types import SimpleNamespace
    from . import signing

    entries = package.payload.get('documents')
    review = package.plan.review

    if (
        not isinstance(entries, list)
        or len(entries) != 2
        or [entry.get('kind') for entry in entries] != ['CONTRACT', 'INVOICE']
    ):
        raise ValidationError(
            'Approved commercial documents must be Contract then Invoice.'
        )

    recipients = controlled_commercial_recipients(review)
    documents = []

    for entry in entries:
        try:
            content = base64.b64decode(
                entry['documentBase64'],
                validate=True,
            )
        except (KeyError, ValueError, TypeError, base64.binascii.Error):
            raise ValidationError(
                'Approved release PDF cannot be decoded.'
            ) from None

        if (
            not content.startswith(b'%PDF-')
            or hashlib.sha256(content).hexdigest() != entry.get('pdf_sha256')
        ):
            raise ValidationError(
                'Approved release PDF integrity verification failed.'
            )

        filename = entry.get('filename')
        if (
            not isinstance(filename, str)
            or not filename.endswith('.pdf')
            or len(filename) > 250
        ):
            raise ValidationError('Invalid approved release PDF filename.')

        documents.append(
            SimpleNamespace(content=content, filename=filename)
        )

    payload = signing.envelope_preview(
        documents,
        review['customer'],
        review['gecc'],
        True,
    )

    signers = payload['recipients']['signers']

    if (
        len(signers) != 2
        or [s.get('routingOrder') for s in signers] != ['1', '2']
        or [s.get('email', '').strip().lower() for s in signers]
            != list(recipients)
    ):
        raise ValidationError('Commercial signer routing is invalid.')

    if [d.get('documentId') for d in payload['documents']] != ['1', '2']:
        raise ValidationError('Commercial document routing is invalid.')

    for document, entry in zip(payload['documents'], entries):
        if document.get('name') != entry['filename']:
            raise ValidationError('Commercial document identity changed.')
        document['documentBase64'] = entry['documentBase64']

    payload['status'] = 'sent'
    payload['emailSubject'] = (
        'GECC FICTIONAL SANDBOX CONTRACT SIGNING TEST'
    )
    payload['emailBlurb'] = (
        'FICTIONAL SOFTWARE TEST ONLY. No actual customer contract, '
        'payment authorization, installation approval, or obligation.'
    )
    payload['transactionId'] = str(attempt_id)

    return payload
