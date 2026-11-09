"""VERIDIAN 4437V: isolated test-only tax evidence audit integration.

Not registered with any operational API or tax posting service.
"""
import os
from django.conf import settings
from django.db import connection, transaction
from rest_framework.exceptions import PermissionDenied

from .services import audit
from .tax_draft_evidence_4437U import prepare_tax_evidence_package


def _require_disposable_test_database():
    name = str(connection.settings_dict.get("NAME", ""))
    allowed_names = (
        ":memory:",
        "file:memorydb_default?mode=memory&cache=shared",
    )
    if not (
        settings.ENVIRONMENT == "development"
        and connection.vendor == "sqlite"
        and name in allowed_names
        and os.environ.get("GECC_SQLITE_PATH") == ":memory:"
        and os.environ.get("VERIDIAN_TAX_AUDIT_TEST_ONLY")
        == "ISOLATED_SQLITE_MEMORY"
    ):
        raise PermissionDenied(
            "Tax evidence audit is restricted to the isolated test database."
        )


@transaction.atomic
def test_only_record_tax_evidence(actor, draft):
    _require_disposable_test_database()
    package = prepare_tax_evidence_package(actor, draft)
    payload = package["payload"]

    event = audit(
        actor,
        "tax_draft.test_evidence_prepared",
        payload["msr_id"],
        {
            "schema": payload["schema"],
            "project_id": payload["project_id"],
            "msr_id": payload["msr_id"],
            "msr_version": payload["msr_version"],
            "evidence_sha256": package["sha256"],
            "test_only": True,
            "tax_entry_verified": False,
            "financial_report_eligible": False,
        },
    )
    return {
        "audit_event_id": str(event.pk),
        "evidence_sha256": package["sha256"],
        "status": "ISOLATED_TEST_AUDIT_ONLY",
        "tax_entry_verified": False,
        "financial_report_eligible": False,
    }
