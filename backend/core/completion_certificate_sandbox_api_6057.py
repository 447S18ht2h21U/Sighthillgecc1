"""Authenticated fictional certificate signing-package preparation.

No DocuSign provider call, envelope creation or transmission.
No actual customer signing authority or completion authorization.
"""

from django.db import transaction

from rest_framework.decorators import (
    api_view,
    permission_classes,
    parser_classes,
)

from rest_framework.parsers import JSONParser

from rest_framework.permissions import IsAuthenticated

from rest_framework.exceptions import ValidationError

from rest_framework.response import Response

from .documents import canonical_hash

from .models import ProjectEvidence

from .distributor_invoice_api_6006 import _reader

from .completion_certificate_preparation_6048 import (
    prepare_project_certificate_preview,
)

from .completion_certificate_retention_6052 import (
    CERTIFICATE_EVIDENCE_KIND,
    validate_retained_certificate,
)

from .completion_certificate_sandbox_package_6056 import (
    SANDBOX_PACKAGE_KIND,
    DESIGNATED_SANDBOX_RECIPIENT,
    prepare_sandbox_certificate_package,
    sandbox_envelope_preview,
    require_designated_sandbox_recipient,
)

from .installation_inspection_transaction_6039 import (
    require_inspection_development_environment,
)


def private_response(data, status=200):

    response = Response(
        data,
        status=status,
    )

    response["Cache-Control"] = "private, no-store"

    response["X-Content-Type-Options"] = "nosniff"

    return response


def single_evidence(msr_id, kind):

    records = list(
        ProjectEvidence.objects
        .select_for_update()
        .filter(
            msr_id=msr_id,
            kind=kind,
        )[:2]
    )

    if len(records) > 1:

        raise ValidationError(
            "Conflicting certificate evidence requires review."
        )

    return records[0] if records else None


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
@transaction.atomic
def completion_certificate_sandbox(request, project_id):

    require_inspection_development_environment()

    actor = _reader(request)

    prepared = prepare_project_certificate_preview(
        actor=actor,
        project_id=project_id,
    )

    certificate = single_evidence(
        prepared["msr_id"],
        CERTIFICATE_EVIDENCE_KIND,
    )

    if certificate is None:

        raise ValidationError(
            "Prepare and retain the Completion Certificate first."
        )

    validate_retained_certificate(
        payload=certificate.data,
        digest=certificate.digest,
    )

    for field in (
        "project_id",
        "msr_id",
        "msr_version",
        "snapshot_sha256",
        "inspection_id",
        "inspection_digest",
        "manifest_sha256",
        "reference_sha256",
        "kind",
        "identity",
    ):

        if certificate.data.get(field) != prepared[field]:

            raise ValidationError(
                "Retained certificate no longer matches "
                "the approved project and inspection."
            )

    if (
        certificate.data.get("prepared_by")
            != str(certificate.created_by_id)
    ):

        raise ValidationError(
            "Retained certificate provenance requires review."
        )

    email = require_designated_sandbox_recipient(
        DESIGNATED_SANDBOX_RECIPIENT
    )

    package = None

    created = False

    if request.method == "POST":

        required = {
            "expected_certificate_id",
            "expected_certificate_digest",
            "sandbox_recipient",
            "fictional_confirmed",
        }

        if (
            type(request.data) is not dict
            or set(request.data) != required
        ):

            raise ValidationError(
                "Complete fictional signing preparation "
                "confirmation is required."
            )

        if (
            request.data["expected_certificate_id"]
                != str(certificate.pk)
            or request.data["expected_certificate_digest"]
                != certificate.digest
        ):

            raise ValidationError(
                "Retained certificate changed. Refresh before proceeding."
            )

        package, created = prepare_sandbox_certificate_package(
            actor=actor,
            project_id=project_id,
            **request.data,
        )

    else:

        package = single_evidence(
            prepared["msr_id"],
            SANDBOX_PACKAGE_KIND,
        )

    layout = None

    if package is not None:

        if canonical_hash(package.data) != package.digest:

            raise ValidationError(
                "Sandbox package fingerprint mismatch."
            )

        for field in (
            "project_id",
            "msr_id",
            "snapshot_sha256",
            "inspection_id",
            "inspection_digest",
        ):

            if package.data.get(field) != prepared[field]:

                raise ValidationError(
                    "Sandbox package no longer matches "
                    "the current approved inspection."
                )

        envelope = sandbox_envelope_preview(
            package=package,
            certificate=certificate,
        )

        if envelope["status"] != "created":

            raise ValidationError(
                "Unexpected sandbox envelope preparation state."
            )

        layout = package.data["layout"]

    return private_response({
        "project_id": prepared["project_id"],
        "msr_id": prepared["msr_id"],
        "inspection_id": prepared["inspection_id"],
        "certificate_id": str(certificate.pk),
        "certificate_digest": certificate.digest,
        "certificate_kind": certificate.data["kind"],
        "pdf_sha256": certificate.data["pdf_sha256"],
        "sandbox_recipient": {
            "name": certificate.data["identity"]["customer_name"],
            "email": email,
            "classification": "DESIGNATED_SANDBOX_RECIPIENT",
            "operational_customer_authority": False,
        },
        "prepared": package is not None,
        "package_id": (
            str(package.pk) if package else None
        ),
        "package_digest": (
            package.digest if package else None
        ),
        "prepared_at": (
            package.data["prepared_at"] if package else None
        ),
        "layout": layout,
        "fictional": True,
        "signed": False,
        "provider_authenticated": False,
        "provider_layout_verified": False,
        "sandbox_send_authorized": False,
        "certificate_send_authorized": False,
        "operational_customer_authority": False,
        "completion_authorized": False,
    }, status=201 if created else 200)
