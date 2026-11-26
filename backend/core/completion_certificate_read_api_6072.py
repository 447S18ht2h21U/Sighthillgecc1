"""Restricted fictional Completion Certificate retrieval interface."""

import os

from django.db import transaction

from rest_framework.decorators import (
    api_view,
    permission_classes,
    parser_classes,
)

from rest_framework.permissions import IsAuthenticated

from rest_framework.parsers import JSONParser

from rest_framework.response import Response

from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from .distributor_invoice_api_6006 import _reader

from .completion_certificate_read_6069 import (
    FLAG,
    PROJECT_ID,
    ENVELOPE_ID,
    SIGNED_KIND,
    begin,
    source_binding,
    validate_retained,
    single_evidence,
)


def private(data):

    response = Response(data)

    response["Cache-Control"] = "private, no-store"

    response["Referrer-Policy"] = "no-referrer"

    response["X-Content-Type-Options"] = "nosniff"

    return response


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def certificate_read(request, project_id):

    if str(project_id) != PROJECT_ID:

        raise PermissionDenied(
            "Designated fictional project required."
        )

    actor = _reader(request)

    if request.method == "POST":

        if (
            type(request.data) is not dict
            or set(request.data) != {
                "envelope_id",
                "confirmed",
            }
            or request.data["envelope_id"] != ENVELOPE_ID
            or request.data["confirmed"] is not True
        ):

            raise ValidationError(
                "Confirm retrieval of the existing fictional envelope."
            )

        return private(begin(
            actor=actor,
            session_key=request.session.session_key,
            project_id=project_id,
            confirmed=True,
        ))

    with transaction.atomic():

        project, msr, binding, expected = source_binding(actor)

        record = single_evidence(
            project,
            SIGNED_KIND,
        )

        documents = []

        retained_at = None

        if record is not None:

            if record.msr_id != msr.pk:

                raise ValidationError(
                    "Retained evidence does not match the approved MSR."
                )

            data = validate_retained(
                record,
                binding,
            )

            retained_at = data["retained_at"]

            documents = [
                {
                    "document_id": row["document_id"],
                    "kind": row["kind"],
                    "pdf_sha256": row["pdf_sha256"],
                    "pages": row["pages"],
                    "size_bytes": row["size_bytes"],
                    "pdf_base64": row["pdf_base64"],
                }
                for row in data["documents"]
            ]

        return private({
            "project_id": PROJECT_ID,
            "msr_id": str(msr.pk),
            "envelope_id": ENVELOPE_ID,
            "retained": record is not None,
            "retained_at": retained_at,
            "documents": documents,
            "read_available": os.environ.get(FLAG) == "1",
            "fictional": True,
            "read_only": True,
            "operational_signature_verified": False,
            "financial_posting_authorized": False,
            "completion_authorized": False,
        })
