"""Read-only reconciliation of approved and purchased equipment.

All results are advisory. This module does not establish installation,
payment, financial posting, substitution or customer release authority.
"""

from collections import Counter

from .equipment_package_requirements_6029 import (
    expand_purchase_requirement,
)

from .equipment_invoice_rows import (
    NEW_MSR_FIELDS,
    project_equipment_rows,
)

from .distributor_equipment_reconciliation_6024 import (
    reconcile_equipment,
)


PURCHASE_CATEGORIES = frozenset({
    "new installation",
    "installing new equipment",
    "new equipment installation",
    "replacing equipment",
    "replacing existing equipment",
})


EXISTING_EQUIPMENT_CATEGORIES = frozenset({
    "service",
    "service maintenance",
    "repair",
})


def approved_purchase_requirements(snapshot):
    """Read approved equipment only; never consult mutable catalog data."""

    if type(snapshot) is not dict:
        raise ValueError(
            "Approved MSR information is unavailable."
        )

    equipment = snapshot.get("equipment")

    if type(equipment) is not list:
        raise ValueError(
            "Approved equipment information is unavailable."
        )

    if not equipment:

        return {
            "required_equipment": [],
            "existing_equipment": [],
        }

    # Reuse established approved equipment row validation.

    project_equipment_rows(snapshot)

    required = []

    existing = []

    for index, row in enumerate(equipment, start=1):

        if (
            type(row) is not dict
            or set(row) != NEW_MSR_FIELDS
        ):
            raise ValueError(
                f"Approved equipment row {index} "
                "requires complete equipment information."
            )

        category = row["category_of_work"]

        if type(category) is not str:
            raise ValueError(
                f"Approved equipment row {index} "
                "has an invalid work category."
            )

        category_key = " ".join(
            category.casefold().split()
        )

        model = row["model_number"]

        quantity = row["quantity"]

        if (
            type(model) is not str
            or not model.strip()
            or type(quantity) is not int
            or not 1 <= quantity <= 999
        ):
            raise ValueError(
                f"Approved equipment row {index} "
                "has invalid identification or quantity."
            )

        item = {
            "model_number": model.strip(),
            "quantity": quantity,
        }

        if category_key in PURCHASE_CATEGORIES:

            required.extend(
                expand_purchase_requirement(
                    model_number=item["model_number"],
                    quantity=item["quantity"],
                )
            )

        elif category_key in EXISTING_EQUIPMENT_CATEGORIES:

            existing.append(item)

        else:

            raise ValueError(
                f"Approved equipment row {index} "
                "requires review of its work category."
            )

    return {
        "required_equipment": required,
        "existing_equipment": existing,
    }


def _collect_purchase_rows(invoice_rows):

    recorded = []

    verified = []

    serials = Counter()

    outstanding_reviews = 0

    for invoice in invoice_rows:

        if invoice.get("current_version") is not True:
            continue

        status = invoice.get("verification_status")

        if status in {
            "REJECTED",
            "HISTORICAL_VERSION",
            "REQUIRES_REVIEW",
        }:

            outstanding_reviews += 1

            continue

        if status not in {
            "NOT_VERIFIED",
            "VERIFIED",
        }:

            outstanding_reviews += 1

            continue

        if invoice.get("equipment_review_recorded") is not True:

            outstanding_reviews += 1

            continue

        for row in invoice["equipment_rows"]:

            item = {
                "model_number": row["model_number"],
                "quantity": row["quantity"],
            }

            recorded.append(item)

            if status == "VERIFIED":

                verified.append(item.copy())

            for serial in row["serial_numbers"]:

                serials[serial.strip().casefold()] += 1

    duplicates = sorted(
        serial
        for serial, count in serials.items()
        if count > 1
    )

    return {
        "recorded": recorded,
        "verified": verified,
        "duplicate_serial_numbers": duplicates,
        "outstanding_invoice_reviews": outstanding_reviews,
    }


def project_equipment_reconciliation(
    *,
    snapshot,
    invoice_rows,
    pending_equipment=None,
):

    result = {
        "status": "REVIEW_REQUIRED",
        "approved_requirements_available": False,
        "required_equipment": [],
        "existing_equipment": [],
        "recorded_purchase_comparison": None,
        "verified_purchase_comparison": None,
        "pending_purchase_comparison": None,
        "duplicate_serial_numbers": [],
        "outstanding_invoice_reviews": 0,
        "recorded_equipment_reconciled": False,
        "verified_equipment_reconciled": False,
        "warnings": [],
        "approved_msr_changed": False,
        "equipment_substitution_authorized": False,
        "physical_installation_verified": False,
        "customer_document_release_authorized": False,
        "financial_posting_authorized": False,
    }

    try:

        requirements = approved_purchase_requirements(
            snapshot
        )

        purchases = _collect_purchase_rows(
            invoice_rows
        )

        required = requirements["required_equipment"]

        result["approved_requirements_available"] = True

        result["required_equipment"] = required

        result["existing_equipment"] = (
            requirements["existing_equipment"]
        )

        result["duplicate_serial_numbers"] = (
            purchases["duplicate_serial_numbers"]
        )

        result["outstanding_invoice_reviews"] = (
            purchases["outstanding_invoice_reviews"]
        )

        recorded = reconcile_equipment(
            approved_equipment=required,
            purchased_equipment=purchases["recorded"],
        )

        verified = reconcile_equipment(
            approved_equipment=required,
            purchased_equipment=purchases["verified"],
        )

        result["recorded_purchase_comparison"] = recorded

        result["verified_purchase_comparison"] = verified

        if pending_equipment is not None:

            pending = reconcile_equipment(
                approved_equipment=required,
                purchased_equipment=(
                    purchases["recorded"]
                    + pending_equipment
                ),
            )

            result["pending_purchase_comparison"] = pending

        if not required:

            result["status"] = (
                "NO_APPROVED_EQUIPMENT_PURCHASE_REQUIRED"
            )

            result["warnings"].append(
                "No new equipment purchases are identified "
                "in the approved MSR. Materials and service "
                "requirements must be reviewed separately."
            )

            if purchases["recorded"] or pending_equipment:

                result["status"] = "EQUIPMENT_REVIEW_REQUIRED"

                result["warnings"].append(
                    "Purchased equipment is present without "
                    "a corresponding approved purchase requirement."
                )

        elif purchases["duplicate_serial_numbers"]:

            result["status"] = "DUPLICATE_SERIAL_REVIEW_REQUIRED"

            result["warnings"].append(
                "The same serial number appears on multiple "
                "current equipment purchase records."
            )

        elif purchases["outstanding_invoice_reviews"]:

            result["status"] = "INVOICE_REVIEW_REQUIRED"

            result["warnings"].append(
                "One or more current invoice records "
                "require additional review."
            )

        else:

            result["recorded_equipment_reconciled"] = (
                recorded["purchase_identifiers_reconciled"]
            )

            result["verified_equipment_reconciled"] = (
                verified["purchase_identifiers_reconciled"]
            )

            if result["verified_equipment_reconciled"]:

                result["status"] = (
                    "VERIFIED_PURCHASE_IDENTIFIERS_RECONCILED"
                )

            elif result["recorded_equipment_reconciled"]:

                result["status"] = (
                    "PURCHASE_VERIFICATION_OUTSTANDING"
                )

            else:

                result["status"] = recorded["status"]

        if result["existing_equipment"]:

            result["warnings"].append(
                "Existing equipment receiving service or repair "
                "is not counted as a required new purchase."
            )

    except (ValueError, TypeError, KeyError) as exc:

        result["status"] = "REVIEW_REQUIRED"

        result["recorded_equipment_reconciled"] = False

        result["verified_equipment_reconciled"] = False

        result["warnings"].append(
            "Equipment reconciliation could not be completed. "
            "Review the approved equipment requirements "
            "and recorded purchases."
        )

    return result
