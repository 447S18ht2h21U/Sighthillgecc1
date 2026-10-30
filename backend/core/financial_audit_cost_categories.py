"""Pure cost-category calculations for VERIDIAN financial audit detail.

This module does not query databases or change financial statement rules.
Amounts are calculated from explicitly supplied approved cost records.
"""

from decimal import Decimal

from .project_cost_services import COST_FIELDS


ZERO = Decimal("0.00")


def summarize_project_cost_categories(records):
    """Summarize individual approved project cost records by field.

    The caller is responsible for selecting the correct records and
    historical reporting cutoff. This function does not choose versions.
    """

    totals = {field: ZERO for field in COST_FIELDS}
    detail = []
    seen_ids = set()

    for record in records:
        record_id = str(record.pk)

        if record_id in seen_ids:
            raise ValueError(
                "Duplicate cost record in audit input."
            )

        seen_ids.add(record_id)

        if record.status != "APPROVED":
            raise ValueError(
                "Only approved project cost records may be summarized."
            )

        categories = {}

        for field in COST_FIELDS:
            amount = Decimal(str(getattr(record, field)))

            if not amount.is_finite() or amount < ZERO:
                raise ValueError(
                    "Cost categories must contain nonnegative finite amounts."
                )

            categories[field] = amount
            totals[field] += amount

        detail.append({
            "cost_record_id": record_id,
            "project_id": str(record.project_id),
            "msr_id": str(record.msr_id),
            "version": record.version,
            "approved_at": (
                record.approved_at.isoformat()
                if record.approved_at else None
            ),
            "categories": {
                field: str(categories[field])
                for field in COST_FIELDS
            },
            "record_total": str(sum(categories.values(), ZERO)),
        })

    grand_total = sum(totals.values(), ZERO)
    detail.sort(
        key=lambda item: (
            item["project_id"],
            item["version"],
            item["cost_record_id"],
        )
    )

    return {
        "category_totals": {
            field: str(totals[field])
            for field in COST_FIELDS
        },
        "grand_total": str(grand_total),
        "record_count": len(detail),
        "records": detail,
        "selection_policy": "CALLER_SUPPLIED_APPROVED_RECORDS",
        "historical_version_selection": "NOT_PERFORMED",
        "financial_statement_reconciled": False,
    }
