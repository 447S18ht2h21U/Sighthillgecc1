"""Isolated test-only tax-entry version storage. No operational migration."""
import json
import os
from uuid import UUID, uuid4

from django.conf import settings
from django.db import connection, transaction, IntegrityError
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import AuditEvent, Outbox, Role, User
from .services import audit
from .tax_draft_evidence_4437U import evidence_package_digest_matches

TABLE = "tax_test_entry_4438p"
GUARD = "tax_test_entry_4438p_immutable"


def require_isolated_tax_test():
    name = str(connection.settings_dict.get("NAME", ""))
    permitted = (
        settings.ENVIRONMENT == "development"
        and connection.vendor == "sqlite"
        and name in (
            ":memory:",
            "file:memorydb_default?mode=memory&cache=shared",
        )
        and os.environ.get("GECC_SQLITE_PATH") == ":memory:"
        and os.environ.get("VERIDIAN_TAX_PERSISTENCE_TEST_ONLY")
        == "ISOLATED_SQLITE_MEMORY"
        and all(
            os.environ.get(f"VERIDIAN_00{n}_TEST_INSTALL")
            == "ISOLATED_SQLITE_MEMORY"
            for n in range(71, 77)
        )
    )
    if not permitted:
        raise PermissionDenied(
            "Tax persistence is restricted to explicitly isolated tests."
        )


def install_disposable_tax_table():
    require_isolated_tax_test()
    with connection.cursor() as cursor:
        cursor.execute(f"""
            CREATE TABLE {TABLE} (
                id TEXT PRIMARY KEY,
                series_id TEXT NOT NULL,
                version INTEGER NOT NULL CHECK(version >= 1),
                prepared_by TEXT NOT NULL,
                evidence_sha256 TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK(status = 'UNVERIFIED_DRAFT_ONLY'),
                UNIQUE(series_id, version)
            )
        """)
        cursor.execute(f"""
            CREATE TRIGGER {GUARD}_update
            BEFORE UPDATE ON {TABLE}
            BEGIN
                SELECT RAISE(ABORT, 'Tax entry version is immutable');
            END
        """)
        cursor.execute(f"""
            CREATE TRIGGER {GUARD}_delete
            BEFORE DELETE ON {TABLE}
            BEGIN
                SELECT RAISE(ABORT, 'Tax entry version is immutable');
            END
        """)


def remove_disposable_tax_table():
    require_isolated_tax_test()
    with connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE}")


def read_disposable_tax_version(entry_id):
    require_isolated_tax_test()
    try:
        identity = str(UUID(str(entry_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValidationError("Invalid tax version identifier.") from exc
    with connection.cursor() as cursor:
        cursor.execute(
            f"""SELECT series_id, version, prepared_by,
                       evidence_sha256, evidence_json, status
                FROM {TABLE} WHERE id = %s""",
            [identity],
        )
        row = cursor.fetchone()
    if row is None:
        raise ValidationError("Tax version not found.")
    return {
        "id": identity,
        "series_id": row[0],
        "version": row[1],
        "prepared_by": row[2],
        "evidence_sha256": row[3],
        "evidence": json.loads(row[4]),
        "status": row[5],
        "independent_tax_entry_verified": False,
        "financial_report_eligible": False,
    }


@transaction.atomic
def store_disposable_tax_version(
    actor, package, *, series_id, version,
    rejection_decision_id=None
):
    require_isolated_tax_test()
    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("Registered Comptroller required.")

    preparer = User.objects.filter(pk=actor.pk).first()
    if (
        preparer is None
        or preparer.is_active is not True
        or preparer.role != Role.COMPTROLLER
    ):
        raise PermissionDenied("Only an active Comptroller prepares drafts.")

    if not evidence_package_digest_matches(package):
        raise ValidationError("Invalid evidence package fingerprint.")

    payload = package["payload"]
    if (
        type(payload) is not dict
        or payload.get("prepared_by") != str(preparer.pk)
        or payload.get("status") != "UNVERIFIED_DRAFT_EVIDENCE_ONLY"
        or payload.get("schema")
        != "VERIDIAN_TAX_DRAFT_EVIDENCE_4437U_V1"
        or payload.get("independent_tax_entry_verified") is not False
        or payload.get("financial_report_eligible") is not False
        or payload.get("tax_posting_authorized") is not False
        or payload.get("tax_filing_authorized") is not False
        or payload.get("tax_payment_authorized") is not False
    ):
        raise ValidationError("Only an unverified preparer-owned draft is allowed.")

    if type(version) is not int or version < 1:
        raise ValidationError("Positive integer tax version required.")

    try:
        series = str(UUID(str(series_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValidationError("Valid version-series identifier required.") from exc

    # Enforce the historical version sequence for this independent series.
    # A duplicate is left for the database UNIQUE constraint to reject.
    with connection.cursor() as cursor:
        cursor.execute(
            f"""SELECT version, evidence_sha256, id, prepared_by
                FROM {TABLE}
                WHERE series_id = %s
                ORDER BY version DESC
                LIMIT 1""",
            [series],
        )
        predecessor = cursor.fetchone()

    if predecessor is None:
        if version != 1:
            raise ValidationError("A tax-entry series must begin at version 1.")
        previous_sha256 = None
    else:
        latest_version, previous_sha256 = predecessor[:2]
        if version < latest_version or version > latest_version + 1:
            raise ValidationError(
                "Tax-entry versions must follow the existing sequence."
            )

    # A new version requires the authenticated CEO rejection of
    # exactly the preceding version. Caller-supplied text is never
    # sufficient to establish a valid correction.
    authenticated_rejection = None
    if predecessor is None:
        if rejection_decision_id is not None:
            raise ValidationError(
                "First tax version cannot reference a rejection."
            )
    elif version == predecessor[0] + 1:
        try:
            rejection_id = str(UUID(str(rejection_decision_id)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValidationError(
                "Authenticated rejection decision required for revision."
            ) from exc

        previous_sha = predecessor[1]
        previous_id = predecessor[2]
        previous_preparer = predecessor[3]

        if (
            previous_preparer != str(preparer.pk)
            or package["sha256"] == previous_sha
        ):
            raise ValidationError(
                "Revision must have the original preparer and new evidence."
            )

        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT entry_id, verifier_id, preparer_id,
                          evidence_sha256, decision, reason
                   FROM tax_test_ceo_decision_4438r
                   WHERE id = %s""",
                [rejection_id],
            )
            decision_row = cursor.fetchone()

        if (
            decision_row is None
            or decision_row[0] != previous_id
            or decision_row[2] != str(preparer.pk)
            or decision_row[3] != previous_sha
            or decision_row[4] != "TEST_CEO_REJECTED_ONLY"
            or not isinstance(decision_row[5], str)
            or not decision_row[5].strip()
        ):
            raise ValidationError(
                "Revision requires the preceding CEO rejection."
            )

        try:
            verifier_pk = UUID(decision_row[1])
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValidationError(
                "Recorded CEO verifier identity is invalid."
            ) from exc

        if str(verifier_pk) == str(preparer.pk):
            raise ValidationError(
                "Self-verification cannot authorize revision."
            )

        decision_event = AuditEvent.objects.filter(
            entity_id=UUID(rejection_id),
            actor_id=verifier_pk,
            action="tax_test.ceo_decision",
        ).first()

        if (
            decision_event is None
            or decision_event.payload.get("test_only") is not True
            or decision_event.payload.get("entry_id") != previous_id
            or decision_event.payload.get("decision")
            != "TEST_CEO_REJECTED_ONLY"
            or decision_event.payload.get("reason") != decision_row[5]
            or decision_event.payload.get("evidence_sha256") != previous_sha
            or not Outbox.objects.filter(event=decision_event).exists()
        ):
            raise ValidationError(
                "Revision rejection audit evidence is invalid."
            )
        authenticated_rejection = rejection_id
    elif rejection_decision_id is not None:
        raise ValidationError(
            "Rejection reference is invalid for this version."
        )

    entry_id = str(uuid4())
    evidence_json = json.dumps(
        package,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f"""INSERT INTO {TABLE}
                (id, series_id, version, prepared_by,
                 evidence_sha256, evidence_json, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [
                entry_id, series, version, str(preparer.pk),
                package["sha256"], evidence_json,
                "UNVERIFIED_DRAFT_ONLY",
            ],
        )

    audit(
        preparer,
        "tax_test.version_prepared",
        UUID(entry_id),
        {
            "test_only": True,
            "series_id": series,
            "version": version,
            "evidence_sha256": package["sha256"],
            "previous_version_sha256": previous_sha256,
            "rejection_decision_id": authenticated_rejection,
            "verification_authorized": False,
            "financial_report_eligible": False,
        },
    )
    return read_disposable_tax_version(entry_id)
