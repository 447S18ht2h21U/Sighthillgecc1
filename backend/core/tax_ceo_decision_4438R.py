"""Isolated CEO decision evidence, not an operational tax verification."""
import json
from uuid import UUID, uuid4

from django.db import connection, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import AuditEvent, Outbox, Role, User
from .services import audit
from .tax_draft_evidence_4437U import evidence_package_digest_matches
from .tax_version_persistence_4438P import (
    TABLE, read_disposable_tax_version, require_isolated_tax_test,
)

DECISION_TABLE = "tax_test_ceo_decision_4438r"


def install_disposable_decision_table():
    require_isolated_tax_test()
    with connection.cursor() as cursor:
        cursor.execute(f"""
            CREATE TABLE {DECISION_TABLE} (
                id TEXT PRIMARY KEY,
                entry_id TEXT NOT NULL UNIQUE,
                verifier_id TEXT NOT NULL,
                preparer_id TEXT NOT NULL,
                evidence_sha256 TEXT NOT NULL,
                decision TEXT NOT NULL
                    CHECK(decision IN (
                        'TEST_CEO_VERIFIED_ONLY',
                        'TEST_CEO_REJECTED_ONLY'
                    )),
                reason TEXT NOT NULL DEFAULT '',
                CHECK(
                    decision <> 'TEST_CEO_REJECTED_ONLY'
                    OR length(trim(reason)) > 0
                ),
                CHECK(verifier_id <> preparer_id),
                FOREIGN KEY(entry_id) REFERENCES {TABLE}(id)
                    ON DELETE RESTRICT
            )
        """)
        for operation in ("UPDATE", "DELETE"):
            cursor.execute(f"""
                CREATE TRIGGER {DECISION_TABLE}_{operation.lower()}
                BEFORE {operation} ON {DECISION_TABLE}
                BEGIN
                    SELECT RAISE(
                        ABORT, 'CEO tax test decision is immutable'
                    );
                END
            """)



        # Test-only SQLite write-boundary guards. These do not replace
        # PostgreSQL locking or operational authorization.
        cursor.execute(f"""
            CREATE TRIGGER {DECISION_TABLE}_latest_insert
            BEFORE INSERT ON {DECISION_TABLE}
            WHEN EXISTS (
                SELECT 1
                FROM {TABLE} earlier
                JOIN {TABLE} newer
                  ON newer.series_id = earlier.series_id
                 AND newer.version > earlier.version
                WHERE earlier.id = NEW.entry_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Outdated tax entry cannot receive CEO decision'
                );
            END
        """)

        cursor.execute(f"""
            CREATE TRIGGER {TABLE}_rejection_insert
            BEFORE INSERT ON {TABLE}
            WHEN NEW.version > 1
             AND NOT EXISTS (
                SELECT 1
                FROM {TABLE} previous
                JOIN {DECISION_TABLE} decision
                  ON decision.entry_id = previous.id
                WHERE previous.series_id = NEW.series_id
                  AND previous.version = NEW.version - 1
                  AND previous.prepared_by = NEW.prepared_by
                  AND decision.decision = 'TEST_CEO_REJECTED_ONLY'
                  AND decision.evidence_sha256 =
                      previous.evidence_sha256
                  AND length(trim(decision.reason)) > 0
             )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Tax revision requires preceding CEO rejection'
                );
            END
        """)

def remove_disposable_decision_table():
    require_isolated_tax_test()
    with connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {DECISION_TABLE}")


@transaction.atomic
def record_disposable_ceo_decision(
    actor, entry_id, *, decision="TEST_CEO_VERIFIED_ONLY", reason=None
):
    """Record a test decision from stored evidence, never caller evidence."""
    require_isolated_tax_test()

    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("Registered CEO required.")

    ceo = User.objects.filter(pk=actor.pk).first()
    if ceo is None or not ceo.is_active or ceo.role != Role.CEO:
        raise PermissionDenied("Only an active CEO may make a test decision.")

    if decision not in (
        "TEST_CEO_VERIFIED_ONLY",
        "TEST_CEO_REJECTED_ONLY",
    ) or type(decision) is not str:
        raise ValidationError("Invalid test CEO decision.")

    if decision == "TEST_CEO_REJECTED_ONLY":
        if (
            type(reason) is not str
            or not reason.strip()
            or len(reason) > 2000
        ):
            raise ValidationError(
                "CEO tax rejection requires a reason of at most 2000 characters."
            )
        reason = reason.strip()
    elif reason is not None:
        raise ValidationError(
            "A rejection reason cannot accompany a verification decision."
        )
    else:
        reason = ""

    entry = read_disposable_tax_version(entry_id)

    # A historical version stays immutable, but cannot receive a new
    # CEO decision after a newer version has been recorded.
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT MAX(version) FROM {TABLE} WHERE series_id = %s",
            [entry["series_id"]],
        )
        latest_version = cursor.fetchone()[0]

    if latest_version != entry["version"]:
        raise ValidationError(
            "Outdated tax-entry version cannot receive a CEO decision."
        )

    if entry["status"] != "UNVERIFIED_DRAFT_ONLY":
        raise ValidationError("Unexpected tax-entry version status.")

    package = entry["evidence"]
    if (
        not evidence_package_digest_matches(package)
        or package.get("sha256") != entry["evidence_sha256"]
        or package.get("payload", {}).get("prepared_by")
        != entry["prepared_by"]
    ):
        raise ValidationError("Persisted tax evidence is inconsistent.")

    try:
        preparer_pk = UUID(entry["prepared_by"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Invalid recorded preparer identity.") from exc

    if str(ceo.pk) == str(preparer_pk):
        raise PermissionDenied("Self-verification is prohibited.")

    prepared_event = AuditEvent.objects.filter(
        entity_id=UUID(entry["id"]),
        action="tax_test.version_prepared",
        actor_id=preparer_pk,
    ).first()

    if (
        prepared_event is None
        or prepared_event.payload.get("test_only") is not True
        or prepared_event.payload.get("evidence_sha256")
        != entry["evidence_sha256"]
        or not Outbox.objects.filter(event=prepared_event).exists()
    ):
        raise ValidationError("Authenticated preparation audit missing.")

    if not User.objects.filter(pk=preparer_pk).exists():
        raise ValidationError("Original preparer record missing.")

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM {DECISION_TABLE} WHERE entry_id = %s",
            [entry["id"]],
        )
        if cursor.fetchone()[0] != 0:
            raise ValidationError("A decision already exists for this version.")

    decision_id = str(uuid4())
    with connection.cursor() as cursor:
        cursor.execute(
            f"""INSERT INTO {DECISION_TABLE}
                (id, entry_id, verifier_id, preparer_id,
                 evidence_sha256, decision, reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [
                decision_id, entry["id"], str(ceo.pk),
                entry["prepared_by"], entry["evidence_sha256"],
                decision, reason,
            ],
        )

    audit(
        ceo, "tax_test.ceo_decision", UUID(decision_id),
        {
            "test_only": True,
            "entry_id": entry["id"],
            "decision": decision,
            "reason": reason,
            "preparer_id": entry["prepared_by"],
            "evidence_sha256": entry["evidence_sha256"],
            "operational_verification_authorized": False,
            "financial_report_eligible": False,
        },
    )
    return {
        "decision_id": decision_id,
        "entry_id": entry["id"],
        "decision": decision,
        "reason": reason,
        "operational_verification_authorized": False,
        "financial_report_eligible": False,
        "tax_posting_authorized": False,
        "tax_filing_authorized": False,
        "tax_payment_authorized": False,
    }
