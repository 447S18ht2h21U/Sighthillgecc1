"""Fictional certificate preview and permanent retention API."""

from base64 import b64encode

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

from .models import ProjectEvidence

from .distributor_invoice_api_6006 import _reader

from .completion_certificate_preparation_6048 import (
    prepare_project_certificate_preview,
)

from .completion_certificate_retention_6052 import (
    CERTIFICATE_EVIDENCE_KIND,
    retain_project_certificate_preview,
    validate_retained_certificate,
    approved_recipient,
)

from .installation_inspection_transaction_6039 import (
    require_inspection_development_environment,
)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
@transaction.atomic
def completion_certificate_preview(request, project_id):

    require_inspection_development_environment()

    actor = _reader(request)

    prepared = prepare_project_certificate_preview(
        actor=actor,
        project_id=project_id,
    )

    retained = None

    created = False

    if request.method == "POST":

        required = {
            "expected_msr_id",
            "expected_inspection_id",
            "fictional_retention_confirmed",
        }

        if (
            type(request.data) is not dict
            or set(request.data) != required
        ):

            raise ValidationError(
                "Complete certificate preparation confirmation required."
            )

        for field in (
            "expected_msr_id",
            "expected_inspection_id",
        ):

            if (
                type(request.data[field]) is not str
                or not request.data[field].strip()
            ):

                raise ValidationError(
                    "Current approved project and inspection required."
                )

        retained, created = retain_project_certificate_preview(
            actor=actor,
            project_id=project_id,
            **request.data,
        )

    else:

        records = list(
            ProjectEvidence.objects.filter(
                msr_id=prepared["msr_id"],
                kind=CERTIFICATE_EVIDENCE_KIND,
            )[:2]
        )

        if len(records) > 1:

            raise ValidationError(
                "Conflicting retained certificates require review."
            )

        if records:

            retained = records[0]

    if retained is not None:

        data = retained.data

        content = validate_retained_certificate(
            payload=data,
            digest=retained.digest,
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

            if data.get(field) != prepared[field]:

                raise ValidationError(
                    "Retained certificate no longer matches "
                    "the approved project and inspection."
                )

        if (
            data.get("prepared_by")
                != str(retained.created_by_id)
        ):

            raise ValidationError(
                "Retained preparing employee requires review."
            )

        if data["recipient"] != approved_recipient(
            retained.msr.snapshot
        ):

            raise ValidationError(
                "Retained recipient information requires review."
            )

        prepared["pdf_bytes"] = content

        prepared["pdf_sha256"] = data["pdf_sha256"]

    content = prepared["pdf_bytes"]

    if len(content) > 15 * 1024 * 1024:

        raise ValidationError(
            "Certificate exceeds the preview size limit."
        )

    response = Response({
        "project_id": prepared["project_id"],
        "msr_id": prepared["msr_id"],
        "msr_version": prepared["msr_version"],
        "kind": prepared["kind"],
        "identity": prepared["identity"],
        "inspection_id": prepared["inspection_id"],
        "inspection_digest": prepared["inspection_digest"],
        "snapshot_sha256": prepared["snapshot_sha256"],
        "manifest_sha256": prepared["manifest_sha256"],
        "reference_sha256": prepared["reference_sha256"],
        "pdf_sha256": prepared["pdf_sha256"],
        "pdf_base64": b64encode(content).decode("ascii"),
        "retained": retained is not None,
        "retained_certificate_id": (
            str(retained.pk) if retained else None
        ),
        "retained_certificate_digest": (
            retained.digest if retained else None
        ),
        "prepared_at": (
            retained.data["prepared_at"] if retained else None
        ),
        "recipient_status": (
            retained.data["recipient"]["status"]
            if retained else "NOT_RETAINED"
        ),
        "recipient_authorized": False,
        "fictional_preview": True,
        "signed": False,
        "certificate_send_authorized": False,
        "completion_authorized": False,
    }, status=201 if created else 200)

    response["Cache-Control"] = "private, no-store"

    response["X-Content-Type-Options"] = "nosniff"

    return response
