"""Prepare inspection equipment from verified purchasing evidence.

This is a read-only inspection manifest.

Purchase serial numbers are proposed for physical confirmation.
No actual physical inspection or installation acceptance is inferred.
"""

from collections import defaultdict

from .documents import canonical_hash

from .equipment_physical_units import (
    physical_units_from_snapshot,
)

from .distributor_project_reconciliation_6025 import (
    PURCHASE_CATEGORIES,
    EXISTING_EQUIPMENT_CATEGORIES,
    project_equipment_reconciliation,
)


def build_installation_equipment_manifest(
    *,
    msr_id,
    snapshot,
    invoice_rows,
):

    result = {
        "msr_id": str(msr_id),
        "snapshot_sha256": canonical_hash(snapshot),
        "available": False,
        "units": [],
        "required_unit_count": 0,
        "purchase_serial_unit_count": 0,
        "all_required_purchase_serials_available": False,
        "distributor_purchase_review_complete": False,
        "physical_installation_verified": False,
        "installation_acceptance_authorized": False,
        "certificate_send_authorized": False,
        "warnings": [],
    }

    try:

        units = physical_units_from_snapshot(
            msr_id=msr_id,
            snapshot=snapshot,
        )

        comparison = project_equipment_reconciliation(
            snapshot=snapshot,
            invoice_rows=invoice_rows,
        )

        if not comparison["approved_requirements_available"]:

            raise ValueError(
                "Approved purchase requirements unavailable."
            )

        verified_by_model = defaultdict(list)

        seen_serials = set()

        current_rows = [
            row
            for row in invoice_rows
            if row.get("current_version") is True
        ]

        duplicate_serials = bool(
            comparison["duplicate_serial_numbers"]
        )

        if duplicate_serials:

            result["warnings"].append(
                "Duplicate purchasing serial numbers require review."
            )

        for invoice in current_rows:

            if (
                invoice.get("verification_status") != "VERIFIED"
                or invoice.get("equipment_review_recorded") is not True
            ):

                continue

            if invoice.get("msr_id") != str(msr_id):

                raise ValueError(
                    "Purchase evidence version mismatch."
                )

            for row in invoice["equipment_rows"]:

                model = row["model_number"].strip().casefold()

                quantity = row["quantity"]

                serial_numbers = row["serial_numbers"]

                if (
                    type(quantity) is not int
                    or quantity <= 0
                    or type(serial_numbers) is not list
                    or len(serial_numbers) != quantity
                ):

                    raise ValueError(
                        "Purchase serial identification is incomplete."
                    )

                for serial in serial_numbers:

                    if type(serial) is not str or not serial.strip():

                        raise ValueError(
                            "Invalid purchase serial number."
                        )

                    key = serial.strip().casefold()

                    if key in seen_serials:

                        duplicate_serials = True

                    seen_serials.add(key)

                    verified_by_model[model].append({
                        "serial_number": serial.strip(),
                        "invoice_id": invoice["invoice_id"],
                        "allocation_id": invoice["allocation_id"],
                        "invoice_number": invoice["invoice_number"],
                    })

        purchase_units = defaultdict(list)

        for unit in units:

            category = " ".join(
                unit.category_of_work.casefold().split()
            )

            if category in PURCHASE_CATEGORIES:

                purchase_units[
                    unit.model_number.strip().casefold()
                ].append(unit)

            elif category not in EXISTING_EQUIPMENT_CATEGORIES:

                raise ValueError(
                    "Physical equipment work category requires review."
                )

        assignments = {}

        if not duplicate_serials:

            for model, expected_units in purchase_units.items():

                candidates = verified_by_model.get(
                    model,
                    [],
                )

                # Do not arbitrarily associate a serial with
                # a physical position when multiple identical
                # units or excess purchases are present.

                if (
                    len(expected_units) == 1
                    and len(candidates) == 1
                ):

                    assignments[
                        expected_units[0].unit_id
                    ] = candidates[0]

        for unit in units:

            category = " ".join(
                unit.category_of_work.casefold().split()
            )

            purchase_required = (
                category in PURCHASE_CATEGORIES
            )

            model_key = (
                unit.model_number.strip().casefold()
            )

            assigned = assignments.get(
                unit.unit_id
            )

            candidates = (
                verified_by_model.get(model_key, [])
                if purchase_required and not duplicate_serials
                else []
            )

            if not purchase_required:

                status = "EXISTING_EQUIPMENT_REVIEW_REQUIRED"

            elif assigned:

                status = "READY_FOR_PHYSICAL_CONFIRMATION"

            elif candidates:

                status = "SERIAL_SELECTION_REQUIRED"

            else:

                status = "VERIFIED_PURCHASE_SERIAL_REQUIRED"

            result["units"].append({
                "unit_id": unit.unit_id,
                "model_number": unit.model_number,
                "category_of_work": unit.category_of_work,
                "purchase_required": purchase_required,
                "purchase_serial_number": (
                    assigned["serial_number"]
                    if assigned else None
                ),
                "purchase_source": (
                    assigned.copy()
                    if assigned else None
                ),
                "serial_candidates": [
                    candidate.copy()
                    for candidate in candidates
                ],
                "status": status,
                "physically_confirmed": False,
            })

        required_count = sum(
            len(items)
            for items in purchase_units.values()
        )

        result["required_unit_count"] = len(units)

        result["purchase_serial_unit_count"] = len(
            assignments
        )

        result[
            "all_required_purchase_serials_available"
        ] = (
            required_count > 0
            and required_count == len(assignments)
            and not duplicate_serials
            and comparison["verified_equipment_reconciled"]
        )

        result[
            "distributor_purchase_review_complete"
        ] = (
            bool(current_rows)
            and all(
                row.get("verification_status") == "VERIFIED"
                and row.get("equipment_review_recorded") is True
                for row in current_rows
            )
            and not duplicate_serials
            and (
                comparison["verified_equipment_reconciled"]
                or (
                    not required_count
                    and comparison["status"] ==
                        "NO_APPROVED_EQUIPMENT_PURCHASE_REQUIRED"
                )
            )
        )

        if duplicate_serials:

            result["warnings"].append(
                "Physical serial assignment is blocked "
                "until duplicate serials are resolved."
            )

        if any(
            unit["status"] == "SERIAL_SELECTION_REQUIRED"
            for unit in result["units"]
        ):

            result["warnings"].append(
                "Select the correct serial number for each "
                "identical or unresolved equipment unit."
            )

        if any(
            not unit["purchase_required"]
            for unit in result["units"]
        ):

            result["warnings"].append(
                "Existing equipment requires separate "
                "physical identification."
            )

        result["available"] = True

    except (ValueError, TypeError, KeyError):

        result["available"] = False

        result["units"] = []

        result["required_unit_count"] = 0

        result["purchase_serial_unit_count"] = 0

        result[
            "all_required_purchase_serials_available"
        ] = False

        result[
            "distributor_purchase_review_complete"
        ] = False

        result["warnings"].append(
            "Approved equipment or purchase evidence "
            "requires review before physical confirmation."
        )

    return result
