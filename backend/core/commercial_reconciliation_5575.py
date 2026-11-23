"""Provider-verified fictional commercial signing evidence and retention.

No envelope creation, sending, automatic retry, or operational signature
authorization. All retained evidence remains classified as sandbox evidence.
"""

import hashlib
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import docusign, release, sandbox, signing_test
from .commercial_send_callback_5573 import build_commercial_payload
from .documents import canonical_hash
from .models import (
    CommercialSigningAttempt,
    CommercialSigningDocument,
    CommercialSigningObservation,
    Project,
    Role,
    User,
)


STATUSES = {'sent', 'delivered', 'signed', 'completed', 'declined', 'voided'}


def validated_timestamp(value):
    parsed = parse_datetime(value) if isinstance(value, str) and len(value) < 100 else None
    if (
        parsed is None
        or timezone.is_naive(parsed)
        or parsed > timezone.now()
    ):
        raise ValidationError('Invalid DocuSign completion timestamp.')
    return parsed


def check_provider_metadata(attempt, package, summary, recipients, documents):
    """Validate the provider envelope against the exact approved PDFs."""
    expected = build_commercial_payload(package, str(attempt.id))
    expected['status'] = 'created'

    status = summary.get('status')
    if (
        summary.get('envelopeId') != attempt.envelope_id
        or status not in STATUSES
    ):
        raise ValidationError('Unexpected commercial envelope identity or status.')

    sandbox.validated_evidence(
        expected,
        {**summary, 'status': 'created'},
        recipients,
        documents,
        attempt.envelope_id,
    )
    return status


def check_completion(summary, recipients):
    completed = validated_timestamp(summary.get('completedDateTime'))
    signers = recipients.get('signers')

    if not isinstance(signers, list) or len(signers) != 2:
        raise ValidationError('Both expected DocuSign signers are required.')

    observed = {}
    for signer in signers:
        if not isinstance(signer, dict):
            raise ValidationError('Invalid signer completion evidence.')
        identifier = signer.get('recipientId')
        if (
            identifier not in {'1', '2'}
            or identifier in observed
            or signer.get('status') != 'completed'
        ):
            raise ValidationError('Both designated signers must complete signing.')

        signed = validated_timestamp(signer.get('signedDateTime'))
        if signed > completed:
            raise ValidationError('Signer timestamp exceeds envelope completion.')
        observed[identifier] = signed.isoformat()

    if set(observed) != {'1', '2'}:
        raise ValidationError('Missing designated signer completion.')

    return completed.isoformat(), observed


def retrieve_completed_documents(attempt, package, token):
    entries = package.payload['documents']
    if [item['kind'] for item in entries] != ['CONTRACT', 'INVOICE']:
        raise ValidationError('Unexpected commercial document set.')

    results = []
    total = 0

    for number, entry in enumerate(entries, 1):
        content = signing_test.pdf_document(
            attempt.account_id, attempt.envelope_id, str(number), token
        )
        total += len(content)
        results.append({
            'document_id': str(number),
            'kind': entry['kind'],
            'filename': (
                f'{attempt.envelope_id}-{entry["kind"]}-SIGNED-SANDBOX.pdf'
            ),
            'content': content,
            'pdf_sha256': hashlib.sha256(content).hexdigest(),
        })

    certificate = signing_test.pdf_document(
        attempt.account_id, attempt.envelope_id, 'certificate', token
    )
    total += len(certificate)

    if total > signing_test.MAX_RETAINED_BYTES:
        raise ValidationError('Commercial signed bundle exceeds its size limit.')

    results.append({
        'document_id': 'certificate',
        'kind': 'DOCUSIGN_CERTIFICATE',
        'filename': f'{attempt.envelope_id}-SANDBOX-CERTIFICATE.pdf',
        'content': certificate,
        'pdf_sha256': hashlib.sha256(certificate).hexdigest(),
    })
    return results


def inspect_provider(attempt, package, token):
    """Read provider evidence; never create or resend an envelope."""
    if not attempt.envelope_id or not attempt.first_send_started_at:
        raise ValidationError('No known sent commercial envelope to inspect.')

    summary = signing_test.provider(
        attempt.account_id, attempt.envelope_id, token
    )
    recipients = signing_test.provider(
        attempt.account_id, attempt.envelope_id, token,
        resource='/recipients?include_tabs=true',
    )
    documents = signing_test.provider(
        attempt.account_id, attempt.envelope_id, token,
        resource='/documents',
    )

    status = check_provider_metadata(
        attempt, package, summary, recipients, documents
    )

    evidence = {
        'purpose': 'FICTIONAL_COMMERCIAL_SANDBOX_EVIDENCE',
        'account_id': attempt.account_id,
        'envelope_id': attempt.envelope_id,
        'package_digest': package.digest,
        'provider_status': status,
        'observed_at': timezone.now().isoformat(),
        'tokens_retained': False,
        'operational_signature_authorized': False,
        'installation_authorized': False,
    }

    rows = []
    if status == 'completed':
        completed_at, signers = check_completion(summary, recipients)
        rows = retrieve_completed_documents(attempt, package, token)
        evidence['completed_at'] = completed_at
        evidence['signers'] = signers
        evidence['retained_hashes'] = [
            {'document_id': row['document_id'], 'pdf_sha256': row['pdf_sha256']}
            for row in rows
        ]

    after = signing_test.provider(
        attempt.account_id, attempt.envelope_id, token
    )
    if any(
        after.get(key) != summary.get(key)
        for key in (
            'envelopeId', 'status',
            'lastModifiedDateTime', 'completedDateTime',
        )
    ):
        raise ValidationError(
            'DocuSign envelope changed during inspection; read again.'
        )

    return evidence, rows


@transaction.atomic
def retain_observation(actor, challenge, attempt_id, evidence, rows):
    """Record verified sandbox evidence atomically; never assert production proof."""
    reference = CommercialSigningAttempt.objects.select_related(
        'package__plan__msr__project'
    ).get(pk=attempt_id)

    Project.objects.select_for_update().get(
        pk=reference.package.plan.msr.project_id
    )

    attempt = CommercialSigningAttempt.objects.select_for_update().get(
        pk=attempt_id
    )

    if (
        not actor.is_active
        or actor.role not in {Role.COMPTROLLER, Role.CEO, Role.SALES_MANAGER}
        or challenge.actor_id != actor.id
        or challenge.consumed_at is None
        or challenge.context.get('operation') != 'COMMERCIAL_SANDBOX_READ'
        or challenge.context.get('commercial_attempt_id') != str(attempt.id)
        or challenge.configuration_digest
            != docusign.configuration_digest(docusign.configuration())
    ):
        raise PermissionDenied('Commercial sandbox read authorization invalid.')

    if (
        actor.role == Role.SALES_MANAGER
        and reference.package.plan.msr.project.reviewer_id != actor.id
    ):
        raise PermissionDenied('Sales Manager is not assigned to this project.')

    if (
        attempt.envelope_id != evidence.get('envelope_id')
        or attempt.account_id != evidence.get('account_id')
        or attempt.package_digest != evidence.get('package_digest')
        or evidence.get('purpose') != 'FICTIONAL_COMMERCIAL_SANDBOX_EVIDENCE'
        or evidence.get('tokens_retained') is not False
        or evidence.get('operational_signature_authorized') is not False
        or evidence.get('installation_authorized') is not False
    ):
        raise ValidationError('Commercial provider evidence binding failed.')

    if CommercialSigningObservation.objects.filter(challenge=challenge).exists():
        raise ValidationError('This commercial read challenge was already recorded.')

    status = evidence.get('provider_status')
    if status not in STATUSES:
        raise ValidationError('Invalid commercial provider status.')

    if status == 'completed':
        if (
            len(rows) != 3
            or {row['document_id'] for row in rows}
                != {'1', '2', 'certificate'}
        ):
            raise ValidationError('Completed commercial bundle is incomplete.')
    elif rows:
        raise ValidationError('Unsigned commercial documents cannot be retained.')

    existing = list(
        CommercialSigningDocument.objects.filter(attempt=attempt)
    )
    if rows and existing:
        expected = {
            row['document_id']: row['pdf_sha256'] for row in rows
        }
        if (
            {d.document_id: d.pdf_sha256 for d in existing} != expected
            or any(
                hashlib.sha256(bytes(d.content)).hexdigest() != d.pdf_sha256
                for d in existing
            )
        ):
            raise ValidationError('Previously retained commercial bundle differs.')
        rows = []

    observation = CommercialSigningObservation.objects.create(
        attempt=attempt,
        challenge=challenge,
        created_by=actor,
        evidence=evidence,
        digest=canonical_hash(evidence),
    )

    for row in rows:
        if hashlib.sha256(row['content']).hexdigest() != row['pdf_sha256']:
            raise ValidationError('Commercial retained PDF integrity failed.')
        CommercialSigningDocument.objects.create(
            attempt=attempt, observation=observation, **row
        )

    attempt.state = (
        'COMPLETED_RETAINED' if status == 'completed'
        else status.upper()
    )
    attempt.save(update_fields=['state'])

    from .services import audit
    audit(
        actor,
        'commercial_signing.sandbox_observation_recorded',
        reference.package.plan.msr.project_id,
        {
            'attempt_id': str(attempt.id),
            'observation_id': str(observation.id),
            'status': attempt.state,
            'evidence_digest': observation.digest,
            'operational_signature_authorized': False,
        },
    )

    return observation
