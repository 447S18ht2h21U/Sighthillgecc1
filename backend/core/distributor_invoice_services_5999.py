"""Authorized distributor invoice transaction services.

Original documents and allocation records are retained permanently.

No service here posts accounts payable, approves project costs,
authorizes vendor payment or accepts an installation.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import PurePath

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from .documents import canonical_hash

from .models import (
    DistributorInvoice,
    DistributorInvoiceAllocation,
    DistributorInvoiceVerification,
    InstallationSchedule,
    Project,
    Role,
    User,
)

from .services import audit

from .employee_authority_policy_6000 import (
    UPLOAD_DISTRIBUTOR_INVOICE,
    VERIFY_DISTRIBUTOR_INVOICE,
    ALLOCATE_EXISTING_INVOICE,
    require_distributor_invoice_authority,
)


MAX_DOCUMENT_BYTES = 15 * 1024 * 1024

MAX_MONEY = Decimal("9999999999.99")

ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


def _actor(actor, action):
    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "pk", None)
    ):
        raise PermissionDenied("Authentication required.")

    current = User.objects.select_for_update().filter(
        pk=actor.pk,
        is_active=True,
    ).first()

    if current is None:
        raise PermissionDenied("Active employee required.")

    return require_distributor_invoice_authority(
        current,
        action,
    )


def _project(actor, project_id):
    project = Project.objects.select_for_update().filter(
        pk=project_id
    ).first()

    if project is None or project.state == "CANCELLED":
        raise PermissionDenied("Active project required.")

    if actor.role == Role.INSTALLATION_MANAGER:
        assigned = InstallationSchedule.objects.filter(
            project=project,
            installation_manager=actor,
            status__in=(
                InstallationSchedule.Status.SCHEDULED,
                InstallationSchedule.Status.COMPLETED,
            ),
        ).exists()

        if not assigned:
            raise PermissionDenied(
                "You are not assigned to this installation."
            )

    msr = project.current_approved

    if (
        msr is None
        or msr.project_id != project.pk
        or msr.status != "APPROVED"
        or type(msr.snapshot) is not dict
    ):
        raise ValidationError(
            "The current approved MSR is required."
        )

    return project, msr


def _text(value, label, maximum):
    if type(value) is not str:
        raise ValidationError(label + " must be text.")

    value = value.strip()

    if not value or len(value) > maximum:
        raise ValidationError(
            "Enter a valid " + label.lower() + "."
        )

    if any(ord(char) < 32 or ord(char) == 127
           for char in value):
        raise ValidationError(
            label + " contains invalid characters."
        )

    return value


def _money(value, label):
    if (
        isinstance(value, bool)
        or not isinstance(value, (str, int, Decimal))
    ):
        raise ValidationError(
            label + " must be an exact monetary amount."
        )

    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(
            label + " is not a valid monetary amount."
        ) from None

    if (
        not result.is_finite()
        or result < 0
        or result > MAX_MONEY
    ):
        raise ValidationError(
            label + " is outside the allowed range."
        )

    if result != result.quantize(Decimal("0.01")):
        raise ValidationError(
            label + " cannot contain fractional cents."
        )

    return result.quantize(Decimal("0.01"))


def _notes(value):
    if type(value) is not str or len(value.strip()) > 2000:
        raise ValidationError("Enter valid notes.")

    return value.strip()


def _document(filename, content_type, content):
    filename = _text(filename, "Filename", 250)

    if (
        "/" in filename
        or chr(92) in filename
        or ":" in filename
        or PurePath(filename).name != filename
        or filename in (".", "..")
    ):
        raise ValidationError(
            "Invalid invoice filename."
        )

    if content_type not in ALLOWED_TYPES:
        raise ValidationError(
            "Upload a PDF, JPEG or PNG invoice."
        )

    if not isinstance(content, bytes):
        raise ValidationError(
            "Original invoice document bytes are required."
        )

    if not content or len(content) > MAX_DOCUMENT_BYTES:
        raise ValidationError(
            "Invoice document exceeds the allowed size."
        )

    signatures = {
        "application/pdf": b"%PDF-",
        "image/jpeg": bytes.fromhex("FFD8FF"),
        "image/png": bytes.fromhex("89504E470D0A1A0A"),
    }

    if not content.startswith(signatures[content_type]):
        raise ValidationError(
            "Invoice file content and file type do not match."
        )

    extensions = {
        "application/pdf": (".pdf",),
        "image/jpeg": (".jpg", ".jpeg"),
        "image/png": (".png",),
    }

    if not filename.lower().endswith(
        extensions[content_type]
    ):
        raise ValidationError(
            "Invoice filename and file type do not match."
        )

    return filename


def _amounts(
    equipment_amount,
    material_amount,
    other_amount,
):
    equipment = _money(
        equipment_amount,
        "Equipment amount",
    )

    materials = _money(
        material_amount,
        "Materials amount",
    )

    other = _money(
        other_amount,
        "Other amount",
    )

    total = equipment + materials + other

    if total <= 0:
        raise ValidationError(
            "A positive project allocation is required."
        )

    return equipment, materials, other, total


def _verify_content(invoice):
    content = bytes(invoice.content or b"")

    if (
        not content
        or sha256(content).hexdigest()
        != invoice.content_sha256
    ):
        raise ValidationError(
            "Original invoice integrity verification failed."
        )


def _allocate_locked(
    *,
    actor,
    invoice,
    project,
    msr,
    equipment_amount,
    material_amount,
    other_amount,
    allocation_notes,
):
    _verify_content(invoice)

    equipment, materials, other, total = _amounts(
        equipment_amount,
        material_amount,
        other_amount,
    )

    notes = _notes(allocation_notes)

    if other > 0 and not notes:
        raise ValidationError(
            "Describe other allocated invoice costs."
        )

    allocations = list(
        DistributorInvoiceAllocation.objects.filter(
            invoice=invoice,
        )
    )

    # Count historical allocations too. An MSR revision cannot
    # silently permit the same expense to be allocated again.
    if any(
        row.project_id == project.pk
        for row in allocations
    ):
        raise ValidationError(
            "This invoice already has an allocation "
            "for this project."
        )

    allocated = sum(
        (row.allocated_total for row in allocations),
        Decimal("0.00"),
    )

    if allocated + total > invoice.invoice_total:
        raise ValidationError(
            "Project allocations cannot exceed the invoice total."
        )

    allocation = DistributorInvoiceAllocation.objects.create(
        invoice=invoice,
        project=project,
        msr=msr,
        equipment_amount=equipment,
        material_amount=materials,
        other_amount=other,
        allocation_notes=notes,
        created_by=actor,
    )

    audit(
        actor,
        "distributor.invoice_allocated",
        project.pk,
        {
            "invoice_id": str(invoice.pk),
            "allocation_id": str(allocation.pk),
            "msr_id": str(msr.pk),
            "allocated_total": str(total),
            "invoice_sha256": invoice.content_sha256,
            "financial_posting_authorized": False,
        },
    )

    return allocation


@transaction.atomic
def record_distributor_invoice(
    *,
    actor,
    project_id,
    distributor_name,
    invoice_number,
    invoice_date,
    invoice_total,
    filename,
    content_type,
    content,
    equipment_amount,
    material_amount,
    other_amount="0.00",
    allocation_notes="",
):
    current = _actor(
        actor,
        UPLOAD_DISTRIBUTOR_INVOICE,
    )

    project, msr = _project(
        current, project_id
    )

    distributor_name = _text(
        distributor_name, "Distributor name", 250
    )

    invoice_number = _text(
        invoice_number, "Invoice number", 150
    )

    if (
        type(invoice_date) is not date
        or invoice_date > timezone.localdate()
    ):
        raise ValidationError(
            "Enter a valid distributor invoice date."
        )

    total = _money(invoice_total, "Invoice total")

    if total <= 0:
        raise ValidationError(
            "Invoice total must be positive."
        )

    filename = _document(
        filename, content_type, content
    )

    digest = sha256(content).hexdigest()

    distributor_key = " ".join(
        distributor_name.casefold().split()
    )

    number_key = " ".join(
        invoice_number.casefold().split()
    )

    if DistributorInvoice.objects.filter(
        distributor_key=distributor_key,
        invoice_number_key=number_key,
    ).exists():
        raise ValidationError(
            "This distributor invoice is already recorded."
        )

    if DistributorInvoice.objects.filter(
        content_sha256=digest,
    ).exists():
        raise ValidationError(
            "This original invoice document is already recorded."
        )

    try:
        with transaction.atomic():
            invoice = DistributorInvoice.objects.create(
                distributor_name=distributor_name,
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                currency="USD",
                invoice_total=total,
                original_filename=filename,
                content_type=content_type,
                content=content,
                uploaded_by=current,
            )
    except IntegrityError:
        raise ValidationError(
            "Invoice could not be recorded. "
            "Check for an existing invoice."
        ) from None

    allocation = _allocate_locked(
        actor=current,
        invoice=invoice,
        project=project,
        msr=msr,
        equipment_amount=equipment_amount,
        material_amount=material_amount,
        other_amount=other_amount,
        allocation_notes=allocation_notes,
    )

    audit(
        current,
        "distributor.invoice_recorded",
        project.pk,
        {
            "invoice_id": str(invoice.pk),
            "allocation_id": str(allocation.pk),
            "invoice_sha256": invoice.content_sha256,
            "invoice_total": str(total),
            "vendor_payment_authorized": False,
        },
    )

    return invoice, allocation


@transaction.atomic
def allocate_existing_invoice(
    *,
    actor,
    project_id,
    invoice_id,
    equipment_amount,
    material_amount,
    other_amount="0.00",
    allocation_notes="",
):
    current = _actor(
        actor,
        ALLOCATE_EXISTING_INVOICE,
    )

    project, msr = _project(
        current, project_id
    )

    invoice = DistributorInvoice.objects.select_for_update().filter(
        pk=invoice_id,
    ).first()

    if invoice is None:
        raise ValidationError(
            "Distributor invoice not found."
        )

    return _allocate_locked(
        actor=current,
        invoice=invoice,
        project=project,
        msr=msr,
        equipment_amount=equipment_amount,
        material_amount=material_amount,
        other_amount=other_amount,
        allocation_notes=allocation_notes,
    )


@transaction.atomic
def verify_distributor_invoice(
    *,
    actor,
    project_id,
    allocation_id,
    invoice_examined,
    allocation_confirmed,
    accept,
    review_notes="",
):
    current = _actor(
        actor,
        VERIFY_DISTRIBUTOR_INVOICE,
    )

    project, msr = _project(
        current, project_id
    )

    if (
        type(accept) is not bool
        or type(invoice_examined) is not bool
        or type(allocation_confirmed) is not bool
    ):
        raise ValidationError(
            "An explicit invoice review decision is required."
        )

    notes = _notes(review_notes)

    allocation = (
        DistributorInvoiceAllocation.objects
        .select_for_update()
        .filter(
            pk=allocation_id,
            project=project,
            msr=msr,
        ).first()
    )

    if allocation is None:
        raise ValidationError(
            "Current project invoice allocation not found."
        )

    invoice = DistributorInvoice.objects.select_for_update().get(
        pk=allocation.invoice_id,
    )

    _verify_content(invoice)

    if DistributorInvoiceVerification.objects.filter(
        allocation=allocation,
    ).exists():
        raise ValidationError(
            "This allocation already has a verification decision. "
            "Use the controlled correction process."
        )

    if accept and not (
        invoice_examined and allocation_confirmed
    ):
        raise ValidationError(
            "Review the original invoice and confirm "
            "the project allocation."
        )

    if not accept and not notes:
        raise ValidationError(
            "Explain why the invoice cannot be verified."
        )

    verification = (
        DistributorInvoiceVerification.objects.create(
            allocation=allocation,
            decision=(
                DistributorInvoiceVerification.Decision.VERIFIED
                if accept else
                DistributorInvoiceVerification.Decision.REJECTED
            ),
            invoice_sha256=invoice.content_sha256,
            snapshot_sha256=canonical_hash(msr.snapshot),
            review_notes=notes,
            verified_by=current,
        )
    )

    audit(
        current,
        "distributor.invoice_reviewed",
        project.pk,
        {
            "invoice_id": str(invoice.pk),
            "allocation_id": str(allocation.pk),
            "verification_id": str(verification.pk),
            "decision": verification.decision,
            "invoice_examined": invoice_examined,
            "allocation_confirmed": allocation_confirmed,
            "invoice_sha256": invoice.content_sha256,
            "vendor_payment_authorized": False,
            "installation_acceptance_established": False,
        },
    )

    return verification
