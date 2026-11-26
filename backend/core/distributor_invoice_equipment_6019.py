"""Reviewed equipment identification from distributor invoices.

Keep purchasing evidence separate from installed equipment,
customer selling prices and customer document release.
"""

import re

from django.db import transaction

from rest_framework.exceptions import ValidationError

from .documents import canonical_hash

from .models import (
    DistributorInvoiceAllocation,
    DistributorInvoiceEquipmentReview,
)

from .services import audit

from .distributor_invoice_services_5999 import (
    _actor,
    _project,
    _verify_content,
)

from .employee_authority_policy_6000 import (
    UPLOAD_DISTRIBUTOR_INVOICE,
)


MAX_EQUIPMENT_ROWS = 250

MAX_SERIAL_NUMBERS = 1000


def _identifier(value, label):

    if type(value) is not str:
        raise ValidationError(
            label + " must be text."
        )

    value = value.strip()

    if not 1 <= len(value) <= 100:
        raise ValidationError(
            "Enter a valid " + label.lower() + "."
        )

    if any(
        ord(character) < 32 or ord(character) == 127
        for character in value
    ):
        raise ValidationError(
            label + " contains invalid characters."
        )

    return value


def validate_equipment_review(
    *,
    equipment_rows,
    no_equipment_on_invoice,
    distributor_invoice_confirmed,
    invoice_details_confirmed,
    equipment_information_confirmed,
):

    confirmations = {
        "distributor_invoice_confirmed":
            distributor_invoice_confirmed,

        "invoice_details_confirmed":
            invoice_details_confirmed,

        "equipment_information_confirmed":
            equipment_information_confirmed,
    }

    for field, value in confirmations.items():

        if value is not True:
            raise ValidationError({
                field: "Employee confirmation is required."
            })

    if type(no_equipment_on_invoice) is not bool:
        raise ValidationError(
            "Confirm whether this allocation contains equipment."
        )

    if type(equipment_rows) is not list:
        raise ValidationError(
            "Equipment information must be a list."
        )

    if len(equipment_rows) > MAX_EQUIPMENT_ROWS:
        raise ValidationError(
            "Too many equipment records for one invoice allocation."
        )

    if bool(equipment_rows) == no_equipment_on_invoice:
        raise ValidationError(
            "Enter the equipment for this project or confirm "
            "that the allocation contains no equipment."
        )

    normalized = []

    seen_serials = set()

    for index, row in enumerate(equipment_rows):

        label = f"Equipment row {index + 1}"

        if type(row) is not dict:
            raise ValidationError(
                label + " is invalid."
            )

        if set(row) != {
            "quantity",
            "model_number",
            "serial_numbers",
        }:
            raise ValidationError(
                label + " contains unexpected or missing information."
            )

        quantity = row["quantity"]

        if (
            type(quantity) is not int
            or not 1 <= quantity <= MAX_SERIAL_NUMBERS
        ):
            raise ValidationError(
                label + " requires a positive whole-number quantity."
            )

        model_number = _identifier(
            row["model_number"],
            label + " model number",
        )

        serial_numbers = row["serial_numbers"]

        if type(serial_numbers) is not list:
            raise ValidationError(
                label + " requires a list of serial numbers."
            )

        if len(serial_numbers) != quantity:
            raise ValidationError(
                label + " requires one serial number for each unit."
            )

        clean_serials = []

        for serial in serial_numbers:

            value = _identifier(
                serial,
                label + " serial number",
            )

            key = value.casefold()

            if key in seen_serials:
                raise ValidationError(
                    "Duplicate equipment serial number detected."
                )

            if key in {
                "unknown",
                "pending",
                "none",
                "n/a",
                "na",
                "not available",
            }:
                raise ValidationError(
                    "Do not use placeholders as equipment serial numbers."
                )

            seen_serials.add(key)

            if len(seen_serials) > MAX_SERIAL_NUMBERS:
                raise ValidationError(
                    "Too many equipment serial numbers."
                )

            clean_serials.append(value)

        normalized.append({
            "quantity": quantity,
            "model_number": model_number,
            "serial_numbers": clean_serials,
        })

    return normalized


@transaction.atomic
def record_invoice_equipment_review(
    *,
    actor,
    project_id,
    allocation_id,
    expected_msr_id,
    equipment_rows,
    no_equipment_on_invoice,
    distributor_invoice_confirmed,
    invoice_details_confirmed,
    equipment_information_confirmed,
):

    current = _actor(
        actor,
        UPLOAD_DISTRIBUTOR_INVOICE,
    )

    project, msr = _project(
        current,
        project_id,
    )

    if str(msr.pk) != str(expected_msr_id):
        raise ValidationError(
            "The approved project version changed."
        )

    normalized = validate_equipment_review(
        equipment_rows=equipment_rows,
        no_equipment_on_invoice=no_equipment_on_invoice,
        distributor_invoice_confirmed=distributor_invoice_confirmed,
        invoice_details_confirmed=invoice_details_confirmed,
        equipment_information_confirmed=equipment_information_confirmed,
    )

    allocation = (
        DistributorInvoiceAllocation.objects
        .select_for_update()
        .select_related("invoice")
        .filter(
            pk=allocation_id,
            project=project,
            msr=msr,
        )
        .first()
    )

    if allocation is None:
        raise ValidationError(
            "The current project invoice allocation was not found."
        )

    _verify_content(allocation.invoice)

    if (
        no_equipment_on_invoice
        and allocation.equipment_amount > 0
    ):
        raise ValidationError(
            "Equipment costs are recorded. Review the purchased "
            "equipment before confirming this allocation."
        )

    if DistributorInvoiceEquipmentReview.objects.filter(
        allocation=allocation
    ).exists():
        raise ValidationError(
            "Equipment review already recorded. "
            "The original review must be preserved."
        )

    review = DistributorInvoiceEquipmentReview.objects.create(
        allocation=allocation,
        invoice_sha256=allocation.invoice.content_sha256,
        snapshot_sha256=canonical_hash(msr.snapshot),
        equipment_rows=normalized,
        no_equipment_on_invoice=no_equipment_on_invoice,
        distributor_invoice_confirmed=True,
        invoice_details_confirmed=True,
        equipment_information_confirmed=True,
        reviewed_by=current,
    )

    audit(
        current,
        "distributor.equipment_review_recorded",
        project.pk,
        {
            "equipment_review_id": str(review.pk),
            "invoice_id": str(allocation.invoice_id),
            "allocation_id": str(allocation.pk),
            "msr_id": str(msr.pk),
            "invoice_sha256": review.invoice_sha256,
            "equipment_rows": len(normalized),
            "equipment_units": sum(
                row["quantity"] for row in normalized
            ),
            "physical_installation_verified": False,
            "customer_document_release_authorized": False,
            "financial_posting_authorized": False,
        },
    )

    return review


def customer_equipment_identifiers(review):
    """Return only the permitted equipment identification fields.

    This function is a data projection, not customer document
    approval or transmission authority.
    """

    normalized = validate_equipment_review(
        equipment_rows=review.equipment_rows,
        no_equipment_on_invoice=review.no_equipment_on_invoice,
        distributor_invoice_confirmed=review.distributor_invoice_confirmed,
        invoice_details_confirmed=review.invoice_details_confirmed,
        equipment_information_confirmed=review.equipment_information_confirmed,
    )

    return [
        {
            "quantity": row["quantity"],
            "model_number": row["model_number"],
            "serial_numbers": list(row["serial_numbers"]),
        }
        for row in normalized
    ]
