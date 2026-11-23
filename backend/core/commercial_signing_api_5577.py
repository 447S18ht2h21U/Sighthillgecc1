"""Controlled commercial signing transaction browser API.

No operational signature assertions and no direct DocuSign provider calls.
"""

import hashlib

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import release
from .commercial_read_oauth_5576 import authorized_reader
from .commercial_signing_5567 import begin_authorization
from .documents import canonical_hash
from .models import (
    CommercialSigningAttempt,
    ReleasePackage,
)


def private(response):
    response['Cache-Control'] = 'private, no-store'
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def describe(package):
    attempt = CommercialSigningAttempt.objects.filter(
        package=package
    ).first()

    result = {
        'package_id': str(package.id),
        'project_id': str(package.plan.msr.project_id),
        'msr_id': str(package.plan.msr_id),
        'release': release.status(package),
        'documents': [
            {
                'kind': item['kind'],
                'filename': item['filename'],
                'pdf_sha256': item['pdf_sha256'],
            }
            for item in package.payload.get('documents', [])
        ],
        'attempt': None,
        'send_available': False,
        'operational_signature_verified': False,
        'installation_authorized': False,
        'sandbox_only': True,
    }

    if attempt is None:
        return result

    observation = attempt.observations.order_by(
        '-created_at', '-id'
    ).first()

    evidence = None

    if observation:
        if canonical_hash(observation.evidence) != observation.digest:
            raise ValidationError(
                'Commercial signing observation integrity failed.'
            )

        evidence = {
            'id': str(observation.id),
            'provider_status': observation.evidence.get('provider_status'),
            'observed_at': observation.evidence.get('observed_at'),
            'sandbox_only': True,
        }

    documents = list(
        attempt.retained_documents.order_by('document_id')
    )

    for document in documents:
        if hashlib.sha256(bytes(document.content)).hexdigest() != document.pdf_sha256:
            raise ValidationError(
                'Retained commercial document integrity failed.'
            )

    result['attempt'] = {
        'id': str(attempt.id),
        'state': attempt.state,
        'envelope_id': attempt.envelope_id or None,
        'send_started': attempt.first_send_started_at is not None,
        'provider_observation': evidence,
        'retained_documents': [
            {
                'kind': document.kind,
                'document_id': document.document_id,
                'pdf_sha256': document.pdf_sha256,
            }
            for document in documents
        ],
        'can_read_existing': bool(
            attempt.envelope_id and attempt.first_send_started_at
        ),
        'can_resend': False,
    }

    return result


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def commercial_transaction(request, package_id):
    package = get_object_or_404(
        ReleasePackage.objects.select_related(
            'plan__msr__project'
        ),
        pk=package_id,
        plan__group='COMMERCIAL',
    )

    authorized_reader(request.user, package.plan.msr.project)

    if request.method == 'GET':
        return private(Response(describe(package)))

    if (
        not isinstance(request.data, dict)
        or request.data.get('fictional_project_confirmed') is not True
        or request.data.get('controlled_recipients_confirmed') is not True
    ):
        raise ValidationError(
            'Explicit fictional-project and controlled-recipient '
            'confirmations are required.'
        )

    result = begin_authorization(
        request.user,
        request.session.session_key,
        package.id,
        fictional_project_confirmed=True,
        controlled_recipients_confirmed=True,
    )

    return private(Response(result))
