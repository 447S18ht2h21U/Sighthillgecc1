"""Synthetic payroll contract fixture for isolated cross-language tests.

Uses the existing pure backend formatter, not the authorized database
entry point. This deliberately does NOT authenticate an actor, retrieve
real compensation, grant permissions, or touch a database.

Never register as an API or deploy as an operational command.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "core.test_document_db_settings_4243"
)

import django
django.setup()

from core.payroll_screen_adapter_4331 import (
    format_authorized_personal_screen_candidate,
)


def synthetic_input(case):
    report = {
        "view": "my_compensation",
        "period_start": "2026-11-02",
        "period_end": "2026-11-08",
        "amount_basis": "full_obligation_not_prorated",
        "employee_records": [{
            "period_start": "2026-11-02",
            "period_end": "2026-11-08",
            "compensation_type": "employee",
            "kind": "BASE",
            "amount": "600.00",
            "status": "APPROVED",
            "status_label": "Approved - Not Yet Paid",
            "payment_evidence_status": "NOT_ISSUED",
            "scheduled_payment_date": None,
            "actual_paid_date": None,
        }],
        "contractor_records": [{
            "period_start": "2026-11-02",
            "period_end": "2026-11-08",
            "compensation_type": "contractor",
            "kind": "COMMISSION",
            "amount": "1250.00",
            "status": "PAID",
            "status_label": "Paid",
            "payment_evidence_status": "TEST_ONLY_UNVERIFIED",
            "payment_issued_at": "2026-11-11T10:00:00Z",
            "contractor_settlement_date": "2026-11-12",
            "scheduled_payment_date": None,
            "actual_paid_date": None,
        }],
    }

    if case == "valid":
        return report
    if case == "private_fields":
        report["bank_account"] = "SECRET-DO-NOT-EXPOSE"
        report["employee_records"][0]["tax_identifier"] = (
            "SECRET-DO-NOT-EXPOSE"
        )
        report["contractor_records"][0]["customer_account"] = (
            "SECRET-DO-NOT-EXPOSE"
        )
        return report
    if case == "bad_status":
        report["employee_records"][0]["status"] = "DRAFT"
        return report
    if case == "bad_amount":
        report["contractor_records"][0]["amount"] = "-5.00"
        return report
    if case == "bad_date":
        report["employee_records"][0]["period_end"] = "2026-10-01"
        return report
    if case == "bad_view":
        report["view"] = "company_payroll"
        return report
    raise ValueError("Unknown synthetic test scenario.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("One synthetic test case required.")
    try:
        report = format_authorized_personal_screen_candidate(
            synthetic_input(sys.argv[1])
        )
    except ValueError:
        raise SystemExit(3) from None

    print(json.dumps(report, sort_keys=True, separators=(",", ":")))