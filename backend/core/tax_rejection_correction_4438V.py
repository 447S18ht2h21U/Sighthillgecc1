"""Test-only rejected tax-entry correction. No operational registration."""
from uuid import UUID

from django.db import connection, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import AuditEvent, Outbox, Role, User
from .services import audit
from .tax_ceo_decision_4438R import DECISION_TABLE
from .tax_draft_evidence_4437U import evidence_package_digest_matches
from .tax_version_persistence_4438P import (
    TABLE,
    read_disposable_tax_version,
    require_isolated_tax_test,
    store_disposable_tax_version,
)


@transaction.atomic
def correct_rejected_tax_version(actor, rejected_entry_id, new_package):
    """Create a new version; never change or approve the rejected version."""
    require_isolated_tax_test()

    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("Registered Comptroller required.")

    preparer = User.objects.filter(pk=actor.pk).first()
    if (
        preparer is None
        or preparer.is_active is not True
        or preparer.role != Role.COMPTROLLER
    ):
        raise PermissionDenied("Only an active Comptroller may correct a draft.")

    old = read_disposable_tax_version(rejected_entry_id)

    if old["prepared_by"] != str(preparer.pk):
        raise PermissionDenied(
            "Only the original Comptroller preparer may use this "
            "test-only correction pathway."
        )

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT MAX(version) FROM {TABLE} WHERE series_id = %s",
            [old["series_id"]],
        )
        latest = cursor.fetchone()[0]

        if latest != old["version"]:
            raise ValidationError(
                "Only the latest rejected version can be corrected."
            )

        cursor.execute(
            f"""SELECT id, verifier_id, decision, reason, evidence_sha256
                FROM {DECISION_TABLE}
                WHERE entry_id = %s""",
            [old["id"]],
        )
        decision = cursor.fetchone()

    if decision is None or decision[2] != "TEST_CEO_REJECTED_ONLY":
        raise ValidationError(
            "A recorded CEO rejection is required before correction."
        )

    decision_id, verifier_id, _, reason, decision_sha = decision

    if not reason.strip() or decision_sha != old["evidence_sha256"]:
        raise ValidationError("Rejected version evidence is inconsistent.")

    event = AuditEvent.objects.filter(
        entity_id=UUID(decision_id),
        actor_id=UUID(verifier_id),
        action="tax_test.ceo_decision",
    ).first()

    if (
        event is None
        or event.payload.get("test_only") is not True
        or event.payload.get("entry_id") != old["id"]
        or event.payload.get("decision") != "TEST_CEO_REJECTED_ONLY"
        or event.payload.get("reason") != reason
        or event.payload.get("evidence_sha256") != old["evidence_sha256"]
        or not Outbox.objects.filter(event=event).exists()
    ):
        raise ValidationError("Original CEO rejection audit is missing.")

    if (
        not evidence_package_digest_matches(new_package)
        or new_package["sha256"] == old["evidence_sha256"]
    ):
        raise ValidationError(
            "A correction must contain new, integrity-checked evidence."
        )

    if new_package["payload"].get("prepared_by") != str(preparer.pk):
        raise PermissionDenied("Correction preparer identity mismatch.")

    corrected = store_disposable_tax_version(
        preparer,
        new_package,
        series_id=old["series_id"],
        version=old["version"] + 1,
        rejection_decision_id=decision_id,
    )

    audit(
        preparer,
        "tax_test.rejection_corrected",
        UUID(corrected["id"]),
        {
            "test_only": True,
            "rejected_entry_id": old["id"],
            "rejection_decision_id": decision_id,
            "previous_evidence_sha256": old["evidence_sha256"],
            "corrected_evidence_sha256": corrected["evidence_sha256"],
            "requires_new_ceo_decision": True,
            "operational_verification_authorized": False,
            "financial_report_eligible": False,
        },
    )

    return {
        "rejected_entry_id": old["id"],
        "rejection_decision_id": decision_id,
        "corrected_entry_id": corrected["id"],
        "corrected_version": corrected["version"],
        "status": "UNVERIFIED_CORRECTION_TEST_ONLY",
        "requires_new_ceo_decision": True,
        "operational_verification_authorized": False,
        "financial_report_eligible": False,
        "tax_posting_authorized": False,
        "tax_filing_authorized": False,
        "tax_payment_authorized": False,
    }
