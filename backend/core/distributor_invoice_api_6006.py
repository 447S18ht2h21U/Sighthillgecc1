"""Authorized distributor invoice employee API.

Uses existing transaction services and approved role policy.

This API does not authorize vendor payment, post accounting
entries, establish installation acceptance or release certificates.
"""

from datetime import date

from .installation_equipment_manifest_6038 import (
    build_installation_equipment_manifest,
)

from .distributor_project_reconciliation_6025 import (
    project_equipment_reconciliation,
)
import json

from .distributor_invoice_equipment_6019 import (
    validate_equipment_review,
    record_invoice_equipment_review,
)
from .models import DistributorInvoiceEquipmentReview

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse

from rest_framework.decorators import (
    api_view,
    parser_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response

from .models import (
    Role,
    User,
    DistributorInvoiceAllocation,
    DistributorInvoiceVerification,
)

from .documents import canonical_hash

from .employee_authority_policy_6000 import (
    distributor_invoice_action_allowed,
    UPLOAD_DISTRIBUTOR_INVOICE,
    VERIFY_DISTRIBUTOR_INVOICE,
    ALLOCATE_EXISTING_INVOICE,
)

from .distributor_invoice_services_5999 import (
    _project,
    _verify_content,
    MAX_DOCUMENT_BYTES,
    record_distributor_invoice,
    allocate_existing_invoice,
    verify_distributor_invoice,
)


def _development():
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
    ):
        raise PermissionDenied(
            "Distributor invoice workspace is not live-enabled."
        )


def _reader(request):
    _development()

    actor = request.user

    current = User.objects.select_for_update().filter(
        pk=actor.pk,
        is_active=True,
        role__in=(
            Role.INSTALLATION_MANAGER,
            Role.COMPTROLLER,
            Role.CEO,
        ),
    ).first()

    if current is None:
        raise PermissionDenied(
            "Authorized employee access required."
        )

    return current


def _fields(payload, required, optional=()):
    required = set(required)
    allowed = required | set(optional)

    if set(payload) - allowed:
        raise ValidationError(
            "Unexpected invoice information."
        )

    if required - set(payload):
        raise ValidationError(
            "Complete all required invoice information."
        )

    if hasattr(payload, "getlist"):
        for key in payload:
            if len(payload.getlist(key)) != 1:
                raise ValidationError(
                    "Duplicate invoice input fields are not allowed."
                )


def _row(allocation, msr):
    invoice = allocation.invoice

    verification_rows = list(
        DistributorInvoiceVerification.objects.filter(
            allocation=allocation,
        )[:2]
    )

    verification = (
        verification_rows[0]
        if len(verification_rows) == 1
        else None
    )

    current_version = allocation.msr_id == msr.pk

    status = "NOT_VERIFIED"

    if len(verification_rows) > 1:
        status = "REQUIRES_REVIEW"

    elif verification is not None:

        matching = (
            current_version
            and verification.invoice_sha256
                == invoice.content_sha256
            and verification.snapshot_sha256
                == canonical_hash(msr.snapshot)
        )

        status = (
            verification.decision
            if matching
            else "REQUIRES_REVIEW"
        )

    if not current_version:
        status = "HISTORICAL_VERSION"

    equipment_review = (
        DistributorInvoiceEquipmentReview.objects
        .filter(allocation=allocation)
        .first()
    )

    equipment_review_recorded = False

    retained_equipment = []

    if equipment_review is not None:

        try:

            normalized_equipment = validate_equipment_review(
                equipment_rows=equipment_review.equipment_rows,
                no_equipment_on_invoice=(
                    equipment_review.no_equipment_on_invoice
                ),
                distributor_invoice_confirmed=(
                    equipment_review.distributor_invoice_confirmed
                ),
                invoice_details_confirmed=(
                    equipment_review.invoice_details_confirmed
                ),
                equipment_information_confirmed=(
                    equipment_review.equipment_information_confirmed
                ),
            )

            evidence_matches = (
                equipment_review.invoice_sha256
                    == invoice.content_sha256
                and equipment_review.snapshot_sha256
                    == canonical_hash(allocation.msr.snapshot)
            )

            if evidence_matches:
                retained_equipment = normalized_equipment
                equipment_review_recorded = True

        except ValidationError:
            equipment_review_recorded = False

    return {
        "equipment_review_recorded": equipment_review_recorded,
        "equipment_rows": retained_equipment,
        "no_equipment_on_invoice": (
            equipment_review.no_equipment_on_invoice
            if equipment_review_recorded else False
        ),
        "physical_installation_verified": False,
        "customer_document_release_authorized": False,
        "invoice_id": str(invoice.pk),
        "allocation_id": str(allocation.pk),
        "msr_id": str(allocation.msr_id),
        "current_version": current_version,
        "distributor_name": invoice.distributor_name,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.isoformat(),
        "invoice_total": str(invoice.invoice_total),
        "filename": invoice.original_filename,
        "content_type": invoice.content_type,
        "equipment_amount": str(allocation.equipment_amount),
        "material_amount": str(allocation.material_amount),
        "other_amount": str(allocation.other_amount),
        "allocated_total": str(allocation.allocated_total),
        "allocation_notes": allocation.allocation_notes,
        "verification_status": status,
        "verified_at": (
            verification.verified_at.isoformat()
            if verification else None
        ),
        "review_notes": (
            verification.review_notes
            if verification else ""
        ),
        "original_document_url": (
            f"/api/distributor-invoices/"
            f"{allocation.project_id}/"
            f"{allocation.pk}/original/"
        ),
    }


def _project_response(actor, project, msr):
    allocations = (
        DistributorInvoiceAllocation.objects
        .filter(project=project)
        .select_related("invoice")
        .defer("invoice__content")
        .order_by("invoice__invoice_date", "pk")
    )

    rows = [
        _row(allocation, msr)
        for allocation in allocations
    ]

    current_rows = [
        row for row in rows
        if row["current_version"]
    ]

    return {
        "project_id": str(project.pk),
        "project_code": project.code,
        "customer_name": project.customer.legal_name,
        "installation_address": project.location,
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "can_upload": distributor_invoice_action_allowed(
            actor.role,
            UPLOAD_DISTRIBUTOR_INVOICE,
        ),
        "can_verify": distributor_invoice_action_allowed(
            actor.role,
            VERIFY_DISTRIBUTOR_INVOICE,
        ),
        "can_allocate": distributor_invoice_action_allowed(
            actor.role,
            ALLOCATE_EXISTING_INVOICE,
        ),
        "invoices": rows,
        "installation_equipment_manifest": (
            build_installation_equipment_manifest(
                msr_id=msr.pk,
                snapshot=msr.snapshot,
                invoice_rows=rows,
            )
        ),
        "equipment_reconciliation": (
            project_equipment_reconciliation(
                snapshot=msr.snapshot,
                invoice_rows=rows,
            )
        ),
        "current_invoice_count": len(current_rows),
        "recorded_verifications_complete": (
            bool(current_rows)
            and all(
                row["verification_status"] == "VERIFIED"
                for row in current_rows
            )
        ),
        "installation_evidence_verified": False,
        "financial_posting_authorized": False,
        "vendor_payment_authorized": False,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
@transaction.atomic
def project_invoices(request, project_id):
    actor = _reader(request)

    project, msr = _project(actor, project_id)

    if request.method == "POST":

        if not distributor_invoice_action_allowed(
            actor.role,
            UPLOAD_DISTRIBUTOR_INVOICE,
        ):
            raise PermissionDenied(
                "You are not authorized to upload distributor invoices."
            )

        _fields(
            request.data,
            (
                "document",
                "expected_msr_id",
                "distributor_name",
                "invoice_number",
                "invoice_date",
                "invoice_total",
                "equipment_amount",
                "material_amount",
                "equipment_rows",
                "no_equipment_on_invoice",
                "distributor_invoice_confirmed",
                "invoice_details_confirmed",
                "equipment_information_confirmed",
            ),
            (
                "other_amount",
                "allocation_notes",
            ),
        )

        if request.data["expected_msr_id"] != str(msr.pk):
            raise ValidationError(
                "The approved project version changed. "
                "Refresh the project before saving."
            )

        document = request.FILES.get("document")

        if (
            document is None
            or document.size <= 0
            or document.size > MAX_DOCUMENT_BYTES
        ):
            raise ValidationError(
                "Choose a PDF, JPEG or PNG file up to 15 MB."
            )

        try:
            invoice_date = date.fromisoformat(
                request.data["invoice_date"]
            )
        except (ValueError, TypeError):
            raise ValidationError(
                "Enter a valid invoice date."
            ) from None

        content = document.read(MAX_DOCUMENT_BYTES + 1)

        if len(content) != document.size:
            raise ValidationError(
                "Invoice upload could not be read completely."
            )

        def read_boolean(name):

            value = request.data[name]

            if value not in ("true", "false"):
                raise ValidationError({
                    name: "An explicit confirmation is required."
                })

            return value == "true"

        raw_equipment = request.data["equipment_rows"]

        if (
            type(raw_equipment) is not str
            or len(raw_equipment) > 200000
        ):
            raise ValidationError(
                "Equipment information exceeds the allowed size."
            )

        try:
            equipment_rows = json.loads(raw_equipment)

        except (ValueError, RecursionError):
            raise ValidationError(
                "Invalid equipment review information."
            ) from None

        confirmations = {
            "no_equipment_on_invoice":
                read_boolean("no_equipment_on_invoice"),

            "distributor_invoice_confirmed":
                read_boolean("distributor_invoice_confirmed"),

            "invoice_details_confirmed":
                read_boolean("invoice_details_confirmed"),

            "equipment_information_confirmed":
                read_boolean("equipment_information_confirmed"),
        }

        equipment_rows = validate_equipment_review(
            equipment_rows=equipment_rows,
            **confirmations,
        )

        invoice, allocation = record_distributor_invoice(
            actor=actor,
            project_id=project.pk,
            distributor_name=request.data["distributor_name"],
            invoice_number=request.data["invoice_number"],
            invoice_date=invoice_date,
            invoice_total=request.data["invoice_total"],
            filename=document.name,
            content_type=document.content_type,
            content=content,
            equipment_amount=request.data["equipment_amount"],
            material_amount=request.data["material_amount"],
            other_amount=request.data.get(
                "other_amount", "0.00"
            ),
            allocation_notes=request.data.get(
                "allocation_notes", ""
            ),
        )

        record_invoice_equipment_review(
            actor=actor,
            project_id=project.pk,
            allocation_id=allocation.pk,
            expected_msr_id=msr.pk,
            equipment_rows=equipment_rows,
            **confirmations,
        )

        return Response(
            _project_response(actor, project, msr),
            status=201,
        )

    return Response(
        _project_response(actor, project, msr)
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def original_document(request, project_id, allocation_id):
    actor = _reader(request)

    project, msr = _project(actor, project_id)

    allocation = (
        DistributorInvoiceAllocation.objects
        .filter(
            pk=allocation_id,
            project=project,
        )
        .select_related("invoice")
        .first()
    )

    if allocation is None:
        raise PermissionDenied(
            "Authorized project invoice required."
        )

    invoice = allocation.invoice

    _verify_content(invoice)

    # Original files are downloads rather than executable
    # inline browser content.

    from django.utils.http import content_disposition_header

    response = HttpResponse(
        bytes(invoice.content),
        content_type="application/octet-stream",
    )

    response["Content-Disposition"] = (
        content_disposition_header(
            True,
            invoice.original_filename,
        )
    )

    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"

    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
@transaction.atomic
def review_invoice(request, project_id, allocation_id):
    actor = _reader(request)

    project, msr = _project(actor, project_id)

    if not isinstance(request.data, dict):
        raise ValidationError(
            "A valid invoice review is required."
        )

    _fields(
        request.data,
        (
            "expected_msr_id",
            "invoice_examined",
            "allocation_confirmed",
            "accept",
        ),
        ("review_notes",),
    )

    if request.data["expected_msr_id"] != str(msr.pk):
        raise ValidationError(
            "The approved project version changed. "
            "Refresh before verifying."
        )

    if not distributor_invoice_action_allowed(
        actor.role,
        VERIFY_DISTRIBUTOR_INVOICE,
    ):
        raise PermissionDenied(
            "Invoice verification authority is required."
        )

    allocation = (
        DistributorInvoiceAllocation.objects
        .filter(
            pk=allocation_id,
            project=project,
            msr=msr,
        )
        .select_related("invoice")
        .first()
    )

    if allocation is None:
        raise ValidationError(
            "Current project invoice allocation not found."
        )

    if request.data["accept"] is True:

        row = _row(allocation, msr)

        if not row["equipment_review_recorded"]:
            raise ValidationError(
                "Complete the equipment information review "
                "before verifying this invoice."
            )

    verify_distributor_invoice(
        actor=actor,
        project_id=project.pk,
        allocation_id=allocation_id,
        invoice_examined=request.data["invoice_examined"],
        allocation_confirmed=request.data["allocation_confirmed"],
        accept=request.data["accept"],
        review_notes=request.data.get("review_notes", ""),
    )

    return Response(
        _project_response(actor, project, msr)
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
@transaction.atomic
def allocate_invoice(request, project_id, invoice_id):
    actor = _reader(request)

    project, msr = _project(actor, project_id)

    if not isinstance(request.data, dict):
        raise ValidationError(
            "A valid project allocation is required."
        )

    _fields(
        request.data,
        (
            "expected_msr_id",
            "equipment_amount",
            "material_amount",
        ),
        (
            "other_amount",
            "allocation_notes",
        ),
    )

    if request.data["expected_msr_id"] != str(msr.pk):
        raise ValidationError(
            "The approved project version changed. "
            "Refresh before allocating costs."
        )

    allocate_existing_invoice(
        actor=actor,
        project_id=project.pk,
        invoice_id=invoice_id,
        equipment_amount=request.data["equipment_amount"],
        material_amount=request.data["material_amount"],
        other_amount=request.data.get("other_amount", "0.00"),
        allocation_notes=request.data.get("allocation_notes", ""),
    )

    return Response(
        _project_response(actor, project, msr),
        status=201,
    )


# STEP 1907P-6013: Read-only local document extraction.

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def extract_invoice(request, project_id):

    from .distributor_invoice_extraction_6012 import (
        extract_distributor_invoice,
        InvoiceExtractionError,
    )

    # Authorize the project and upload action before reading
    # the submitted document. Do not hold database locks
    # during potentially slow local document extraction.

    with transaction.atomic():

        actor = _reader(request)

        if not distributor_invoice_action_allowed(
            actor.role,
            UPLOAD_DISTRIBUTOR_INVOICE,
        ):
            raise PermissionDenied(
                "Invoice upload authority is required."
            )

        project, msr = _project(actor, project_id)

        approved_id = str(msr.pk)

        _fields(
            request.data,
            ("document", "expected_msr_id"),
        )

        if request.data["expected_msr_id"] != approved_id:
            raise ValidationError(
                "The approved project version changed. "
                "Refresh before reading this invoice."
            )

        document = request.FILES.get("document")

        if (
            document is None
            or document.size <= 0
            or document.size > MAX_DOCUMENT_BYTES
        ):
            raise ValidationError(
                "Choose a PDF, JPEG or PNG file up to 15 MB."
            )

        content = document.read(MAX_DOCUMENT_BYTES + 1)

        if len(content) != document.size:
            raise ValidationError(
                "Invoice document could not be read completely."
            )

        content_type = document.content_type

    try:

        extracted = extract_distributor_invoice(
            content,
            content_type,
        )

    except InvoiceExtractionError as exc:

        raise ValidationError(str(exc)) from None

    # Recheck authority and project version after extraction.

    with transaction.atomic():

        actor = _reader(request)

        if not distributor_invoice_action_allowed(
            actor.role,
            UPLOAD_DISTRIBUTOR_INVOICE,
        ):
            raise PermissionDenied(
                "Invoice upload authority is required."
            )

        project, msr = _project(actor, project_id)

        if str(msr.pk) != approved_id:
            raise ValidationError(
                "The approved project version changed. "
                "Refresh before continuing."
            )

    # Return suggestions only. Nothing is saved or verified.
    # Raw extracted text is not needed by this screen.

    extracted.pop("review_text", None)

    extracted["project_id"] = str(project_id)

    extracted["msr_id"] = approved_id

    extracted["invoice_saved"] = False

    pending_equipment = []

    unresolved_extraction_rows = 0

    for candidate in extracted["equipment_candidates"]:

        quantities = candidate["quantity_candidates"]

        model = candidate["model_number"]

        if (
            not model
            or len(quantities) != 1
        ):

            unresolved_extraction_rows += 1

            continue

        pending_equipment.append({
            "model_number": model,
            "quantity": quantities[0],
        })

    # Re-read the current project and retained invoice records
    # under the same authorization boundary.

    with transaction.atomic():

        actor = _reader(request)

        if not distributor_invoice_action_allowed(
            actor.role,
            UPLOAD_DISTRIBUTOR_INVOICE,
        ):
            raise PermissionDenied(
                "Invoice upload authority is required."
            )

        project, msr = _project(actor, project_id)

        if str(msr.pk) != approved_id:
            raise ValidationError(
                "The approved project version changed. "
                "Refresh before continuing."
            )

        allocations = (
            DistributorInvoiceAllocation.objects
            .filter(project=project)
            .select_related("invoice")
            .defer("invoice__content")
            .order_by("invoice__invoice_date", "pk")
        )

        invoice_rows = [
            _row(allocation, msr)
            for allocation in allocations
        ]

        extracted["equipment_reconciliation"] = (
            project_equipment_reconciliation(
                snapshot=msr.snapshot,
                invoice_rows=invoice_rows,
                pending_equipment=pending_equipment,
            )
        )

        extracted["unresolved_extraction_rows"] = (
            unresolved_extraction_rows
        )

    response = Response(extracted)

    response["Cache-Control"] = "private, no-store"

    return response
