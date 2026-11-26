"""Compare approved equipment requirements with purchasing evidence.

This module is advisory only.

It cannot modify approved MSRs, substitute equipment identifiers,
establish physical installation, or authorize financial transactions.
"""

from collections import defaultdict


MAX_ROWS = 1000

MAX_UNITS = 10000


# Common OCR confusions in equipment model identifiers.
# These are used to suggest possible matches only.

OCR_EQUIVALENTS = (
    frozenset(("0", "O")),
    frozenset(("1", "I", "L")),
    frozenset(("2", "Z")),
    frozenset(("5", "S")),
    frozenset(("6", "G")),
    frozenset(("8", "B")),
)


def _model(value):

    if type(value) is not str:
        raise ValueError(
            "Equipment model number must be text."
        )

    value = value.strip()

    if not 1 <= len(value) <= 100:
        raise ValueError(
            "Equipment model number is missing or invalid."
        )

    if any(
        ord(character) < 32 or ord(character) == 127
        for character in value
    ):
        raise ValueError(
            "Equipment model number contains invalid characters."
        )

    return value


def _quantity(value):

    if (
        type(value) is not int
        or not 1 <= value <= MAX_UNITS
    ):
        raise ValueError(
            "Equipment quantity must be a positive whole number."
        )

    return value


def _normalize_rows(rows):

    if type(rows) is not list:
        raise ValueError(
            "Equipment information must be a list."
        )

    if len(rows) > MAX_ROWS:
        raise ValueError(
            "Equipment information exceeds the review limit."
        )

    result = []

    for row in rows:

        if type(row) is not dict:
            raise ValueError(
                "Equipment record is invalid."
            )

        if not {
            "model_number",
            "quantity",
        }.issubset(row):
            raise ValueError(
                "Equipment model number and quantity are required."
            )

        model = _model(row["model_number"])

        quantity = _quantity(row["quantity"])

        result.append({
            "model_number": model,
            "quantity": quantity,
        })

    if sum(
        row["quantity"]
        for row in result
    ) > MAX_UNITS:
        raise ValueError(
            "Equipment quantity exceeds the review limit."
        )

    return result


def _possible_ocr_match(observed, expected):

    observed = observed.upper()

    expected = expected.upper()

    if (
        observed == expected
        or len(observed) != len(expected)
    ):
        return False

    differences = 0

    for left, right in zip(observed, expected):

        if left == right:
            continue

        differences += 1

        if differences > 2:
            return False

        if not any(
            left in group and right in group
            for group in OCR_EQUIVALENTS
        ):
            return False

    return differences > 0


def reconcile_equipment(
    *,
    approved_equipment,
    purchased_equipment,
):

    approved = _normalize_rows(
        approved_equipment
    )

    purchased = _normalize_rows(
        purchased_equipment
    )

    expected_quantities = defaultdict(int)

    purchased_quantities = defaultdict(int)

    expected_labels = {}

    for row in approved:

        key = row["model_number"].casefold()

        expected_labels.setdefault(
            key,
            row["model_number"],
        )

        expected_quantities[key] += row["quantity"]

    purchase_results = []

    for row in purchased:

        observed = row["model_number"]

        key = observed.casefold()

        quantity = row["quantity"]

        if key in expected_quantities:

            purchased_quantities[key] += quantity

            purchase_results.append({
                "observed_model_number": observed,
                "quantity": quantity,
                "status": "EXACT_MATCH",
                "suggested_model_number": None,
                "possible_matches": [],
                "employee_confirmation_required": True,
            })

            continue

        possibilities = [
            expected_labels[expected_key]
            for expected_key in expected_quantities
            if _possible_ocr_match(
                observed,
                expected_labels[expected_key],
            )
        ]

        possibilities.sort()

        if len(possibilities) == 1:

            status = "POSSIBLE_OCR_MATCH"

            suggestion = possibilities[0]

        elif len(possibilities) > 1:

            status = "AMBIGUOUS_MODEL"

            suggestion = None

        else:

            status = "UNEXPECTED_MODEL"

            suggestion = None

        purchase_results.append({
            "observed_model_number": observed,
            "quantity": quantity,
            "status": status,
            "suggested_model_number": suggestion,
            "possible_matches": possibilities,
            "employee_confirmation_required": True,
        })

        # Possible matches do not count as confirmed purchases
        # until the employee corrects the observed information.

    requirements = []

    for key, required in expected_quantities.items():

        recorded = purchased_quantities.get(key, 0)

        if recorded == required:

            status = "QUANTITY_MATCH"

        elif recorded == 0:

            status = "NOT_YET_RECORDED"

        elif recorded < required:

            status = "ADDITIONAL_QUANTITY_REQUIRED"

        else:

            status = "EXCESS_QUANTITY_RECORDED"

        requirements.append({
            "approved_model_number": expected_labels[key],
            "approved_quantity": required,
            "recorded_purchase_quantity": recorded,
            "remaining_quantity": max(
                required - recorded,
                0,
            ),
            "excess_quantity": max(
                recorded - required,
                0,
            ),
            "status": status,
        })

    unresolved = [
        row
        for row in purchase_results
        if row["status"] != "EXACT_MATCH"
    ]

    quantity_differences = [
        row
        for row in requirements
        if row["status"] != "QUANTITY_MATCH"
    ]

    identifiers_reconciled = (
        bool(approved)
        and not unresolved
        and not quantity_differences
    )

    if not approved:

        status = "APPROVED_REQUIREMENTS_UNAVAILABLE"

    elif unresolved:

        status = "EQUIPMENT_REVIEW_REQUIRED"

    elif quantity_differences:

        status = "PURCHASE_QUANTITIES_OUTSTANDING"

    else:

        status = "PURCHASE_IDENTIFIERS_RECONCILED"

    return {
        "status": status,
        "approved_equipment": requirements,
        "purchased_equipment": purchase_results,
        "approved_unit_count": sum(
            expected_quantities.values()
        ),
        "exactly_matched_purchase_unit_count": sum(
            purchased_quantities.values()
        ),
        "unresolved_purchase_row_count": len(unresolved),
        "purchase_identifiers_reconciled":
            identifiers_reconciled,
        "employee_confirmation_required": True,
        "approved_msr_changed": False,
        "equipment_substitution_authorized": False,
        "purchase_verification_established": False,
        "physical_installation_verified": False,
        "customer_document_release_authorized": False,
        "financial_posting_authorized": False,
    }
