"""Authenticated development-only integrated inspection API.

No customer document issuance, payment, certificate transmission
or trusted physical installation authority is granted.
"""

from django.db import transaction

from rest_framework.decorators import (
    api_view,
    permission_classes,
    parser_classes,
)

from rest_framework.parsers import JSONParser

from rest_framework.permissions import IsAuthenticated

from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from rest_framework.response import Response

from .documents import canonical_hash

from .models import (
    Role,
    InstallationSchedule,
    ProjectEvidence,
    DistributorInvoiceAllocation,
)

from .distributor_invoice_api_6006 import (
    _reader,
    _row,
)

from .distributor_invoice_services_5999 import (
    _project,
    _verify_content,
)

from .installation_equipment_manifest_6038 import (
    build_installation_equipment_manifest,
)

from .installation_inspection_transaction_6039 import (
    INSPECTION_KIND,
    require_inspection_development_environment,
    record_integrated_installation_inspection,
)


FICTIONAL_PROJECT_CODE = "101-SA-2026-10-05"

FICTIONAL_CUSTOMER_NAME = "GECC Test Customer"


SUBMISSION_FIELDS = frozenset({
    "expected_msr_id",
    "expected_snapshot_sha256",
    "expected_manifest_sha256",
    "equipment_confirmations",
    "findings",
    "fictional_acceptance_test",
})


def _inspection_context(request, project_id):

    require_inspection_development_environment()

    actor = _reader(request)

    if actor.role != Role.INSTALLATION_MANAGER:

        raise PermissionDenied(
            "Only the assigned Installation Manager "
            "may record this inspection."
        )

    project, msr = _project(
        actor,
        project_id,
    )

    schedules = list(
        InstallationSchedule.objects
        .select_for_update()
        .filter(
            project=project,
            installation_manager=actor,
            status=InstallationSchedule.Status.COMPLETED,
        )[:2]
    )

    if len(schedules) != 1:

        raise ValidationError(
            "A completed installation assigned "
            "to you is required."
        )

    return actor, project, msr


def _fictional_project_allowed(project):

    return (
        project.code == FICTIONAL_PROJECT_CODE
        and project.customer.legal_name
            == FICTIONAL_CUSTOMER_NAME
    )


def _validated_submission(payload):

    if (
        type(payload) is not dict
        or set(payload) != SUBMISSION_FIELDS
    ):

        raise ValidationError(
            "Complete inspection information is required."
        )

    for field in (
        "expected_msr_id",
        "expected_snapshot_sha256",
        "expected_manifest_sha256",
    ):

        if (
            type(payload[field]) is not str
            or not payload[field].strip()
        ):

            raise ValidationError(
                "Current project and evidence "
                "identifiers are required."
            )

    for field in (
        "expected_snapshot_sha256",
        "expected_manifest_sha256",
    ):

        value = payload[field]

        if (
            len(value) != 64
            or any(
                character not in "0123456789abcdefABCDEF"
                for character in value
            )
        ):

            raise ValidationError(
                "Inspection evidence fingerprint is invalid."
            )

    if payload["fictional_acceptance_test"] is not True:

        raise ValidationError(
            "Confirm that this is a fictional acceptance test."
        )

    if type(payload["equipment_confirmations"]) is not list:

        raise ValidationError(
            "Equipment confirmations are required."
        )

    if len(payload["equipment_confirmations"]) > 10000:

        raise ValidationError(
            "Equipment confirmation limit exceeded."
        )

    if type(payload["findings"]) is not dict:

        raise ValidationError(
            "Inspection findings are required."
        )

    return {
        field: payload[field]
        for field in SUBMISSION_FIELDS
    }


def _saved_inspection(project, msr):

    records = list(
        ProjectEvidence.objects.filter(
            msr=msr,
            kind=INSPECTION_KIND,
        )[:2]
    )

    if len(records) > 1:

        raise ValidationError(
            "Conflicting inspection records require review."
        )

    if not records:

        return None

    record = records[0]

    payload = record.data

    if (
        type(payload) is not dict
        or canonical_hash(payload) != record.digest
        or payload.get("purpose")
            != "INTEGRATED_INSTALLATION_INSPECTION"
        or payload.get("project_id") != str(project.pk)
        or payload.get("msr_id") != str(msr.pk)
        or payload.get("msr_version") != msr.number
        or payload.get("snapshot_sha256")
            != canonical_hash(msr.snapshot)
        or payload.get("recorded_by")
            != str(record.created_by_id)
        or payload.get("fictional_acceptance_test")
            is not True
        or payload.get("trusted_installation_evidence")
            is not False
        or payload.get("certificate_send_authorized")
            is not False
        or payload.get("installation_acceptance_authorized")
            is not False
        or payload.get("status") not in {
            "INTERNAL_ACCEPTANCE_CANDIDATE",
            "CORRECTIONS_REQUIRED",
        }
    ):

        raise ValidationError(
            "Existing inspection evidence "
            "could not be validated."
        )

    return {
        "inspection_id": str(record.pk),
        "digest": record.digest,
        "status": payload["status"],
        "recorded_at": payload["recorded_at"],
        "equipment": payload["equipment"],
        "findings": payload["findings"],
        "fictional_acceptance_test": True,
        "trusted_installation_evidence": False,
        "installation_acceptance_authorized": False,
        "certificate_send_authorized": False,
    }


def _workspace(project, msr):

    allocations = list(
        DistributorInvoiceAllocation.objects
        .select_for_update()
        .filter(
            project=project,
            msr=msr,
        )
        .select_related("invoice")
        .order_by("invoice__invoice_date", "pk")
    )

    rows = []

    for allocation in allocations:

        _verify_content(allocation.invoice)

        rows.append(
            _row(allocation, msr)
        )

    manifest = build_installation_equipment_manifest(
        msr_id=msr.pk,
        snapshot=msr.snapshot,
        invoice_rows=rows,
    )

    saved = _saved_inspection(
        project,
        msr,
    )

    fictional_allowed = _fictional_project_allowed(
        project
    )

    # Include invoice review status and source references.
    # Confidential costs are not needed in this inspection API.

    invoice_summary = [
        {
            "invoice_id": row["invoice_id"],
            "allocation_id": row["allocation_id"],
            "distributor_name": row["distributor_name"],
            "invoice_number": row["invoice_number"],
            "invoice_date": row["invoice_date"],
            "verification_status": (
                row["verification_status"]
            ),
            "equipment_review_recorded": (
                row["equipment_review_recorded"]
            ),
            "original_document_url": (
                row["original_document_url"]
            ),
        }
        for row in rows
    ]

    return {
        "project_id": str(project.pk),
        "project_code": project.code,
        "customer_name": project.customer.legal_name,
        "installation_address": project.location,
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "manifest_sha256": canonical_hash(manifest),
        "equipment_manifest": manifest,
        "invoice_summary": invoice_summary,
        "saved_inspection": saved,
        "fictional_acceptance_test_required": True,
        "can_record_inspection": (
            fictional_allowed
            and saved is None
            and manifest["available"] is True
        ),
        "can_send_certificate": False,
        "trusted_installation_evidence": False,
        "installation_acceptance_authorized": False,
        "customer_document_release_authorized": False,
        "financial_posting_authorized": False,
        "completion_authorized": False,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
@transaction.atomic
def integrated_installation_inspection(request, project_id):

    actor, project, msr = _inspection_context(
        request,
        project_id,
    )

    if request.method == "POST":

        if not _fictional_project_allowed(project):

            raise PermissionDenied(
                "Inspection recording is currently limited "
                "to the designated fictional acceptance project."
            )

        payload = _validated_submission(
            request.data
        )

        record_integrated_installation_inspection(
            actor=actor,
            project_id=project.pk,
            **payload,
        )

    response = Response(
        _workspace(project, msr),
        status=201 if request.method == "POST" else 200,
    )

    response["Cache-Control"] = "private, no-store"

    return response
