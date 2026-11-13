"""Step 1907P-4689: disposable file-backed catalog acceptance.

Copies a consistent live SQLite snapshot to an isolated temporary file.
Never connects Django to the original development database.
Never enables persistent imports outside this subprocess.
"""
import hashlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from contextlib import closing
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SOURCE = BACKEND / "dev.sqlite3"

sys.path.insert(0, str(BACKEND))


def stop(message):
    raise RuntimeError("SAFETY STOP: " + message)


def fingerprint(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def counts():
    from core.models import (
        AuditEvent, EquipmentCatalogItem, Outbox,
        ProductCatalogCollection, ProductCatalogMembership,
        Project, User,
    )

    return {
        "users": User.objects.count(),
        "projects": Project.objects.count(),
        "equipment": EquipmentCatalogItem.objects.count(),
        "catalogs": ProductCatalogCollection.objects.count(),
        "memberships": ProductCatalogMembership.objects.count(),
        "audits": AuditEvent.objects.count(),
        "outbox": Outbox.objects.count(),
    }


def audit_state():
    from core.models import AuditEvent, AuditHead

    head = AuditHead.objects.get(pk=1)
    last = AuditEvent.objects.order_by("-sequence").first()

    if last is None or head.sequence != last.sequence or head.digest != last.digest:
        stop("Audit head does not match latest event.")

    return head.sequence, head.digest


def verify_new_chain(previous_sequence, previous_digest, amount, actor):
    from core.models import AuditEvent, Outbox

    events = list(
        AuditEvent.objects.filter(
            sequence__gt=previous_sequence
        ).order_by("sequence")
    )

    if len(events) != amount:
        stop("Unexpected number of new audit events.")

    digest = previous_digest

    for offset, event in enumerate(events, start=1):
        if event.sequence != previous_sequence + offset:
            stop("Audit sequence is not contiguous.")

        if event.previous_hash != digest or not event.digest:
            stop("Audit hash linkage failed.")

        if event.actor_id != actor.pk:
            stop("Audit actor differs from authorized manager.")

        if Outbox.objects.filter(event_id=event.pk).count() != 1:
            stop("Audit outbox event is missing or duplicated.")

        digest = event.digest

    if audit_state() != (previous_sequence + amount, digest):
        stop("Audit head differs after import.")


CSV_VALID = (
    "brand,residential_system_type,model_number,description\n"
    "Carrier,Heat Pump,FB-4689-HP,File-backed acceptance fixture\n"
    "Carrier,Furnace,FB-4689-FN,File-backed acceptance fixture\n"
).encode("utf-8")

CSV_ROLLBACK = (
    "brand,residential_system_type,model_number,description\n"
    "Lennox,Heat Pump,FB-4689-L1,Rollback fixture first row\n"
    "Lennox,Furnace,FB-4689-L2,Rollback fixture second row\n"
).encode("utf-8")

CSV_DENIED = (
    "brand,residential_system_type,model_number,description\n"
    "Trane,Heat Pump,FB-4689-DENIED,Unauthorized fixture\n"
).encode("utf-8")


def exercise_copy():
    import django
    from django.conf import settings
    from django.core.exceptions import PermissionDenied
    from django.db import connection

    django.setup()

    from core import catalog_bulk_import_service_4670 as service
    from core import catalog_persistent_activation_policy_4688 as policy
    from core.models import Role, User

    configured = Path(settings.DATABASES["default"]["NAME"]).resolve()
    expected = Path(os.environ["GECC_SQLITE_PATH"]).resolve()

    if configured != expected or configured == SOURCE.resolve():
        stop("Django is not isolated from the development database.")

    if connection.vendor != "sqlite" or not settings.DEBUG:
        stop("Incorrect isolated development configuration.")

    manager = User.objects.filter(
        is_active=True,
        role__in=(Role.SALES_MANAGER, Role.INSTALLATION_MANAGER),
    ).order_by("pk").first()

    associate = User.objects.filter(
        is_active=True,
        role=Role.SALES_ASSOCIATE,
    ).order_by("pk").first()

    if manager is None or associate is None:
        stop("Required existing test identities are unavailable.")

    before = counts()
    sequence, digest = audit_state()

    if before["users"] != 8 or before["projects"] != 3:
        stop("Historical user or project inventory differs.")

    if before["equipment"] != 15:
        stop("Expected 15 existing Ruud configurations.")

    print("PASS: Verified source snapshot configured as file-backed SQLite.")
    print("PASS: Existing manager and unauthorized associate identified.")
    print("PASS: Historical data and audit head established.")

    # The installed activation lock must fail on a real file-backed DB.
    try:
        service.import_catalog_csv_persistent(
            actor_id=manager.pk,
            content=CSV_VALID,
            name="Carrier Acceptance 4689",
            description="Disposable file-backed test",
        )
    except RuntimeError as exc:
        if "not activated" not in str(exc).lower():
            raise
    else:
        stop("Persistent import was allowed without activation.")

    if counts() != before or audit_state() != (sequence, digest):
        stop("Default-deny invocation changed records.")

    print("PASS: Real file-backed import rejected by default activation lock.")

    # Override the lock only in this disposable subprocess.
    # Point the policy's expected BASE_DIR at the temporary directory
    # containing the copied dev.sqlite3, never the actual backend.
    with patch.object(policy, "ACTIVATION_APPROVED", True), \
         patch.object(settings, "BASE_DIR", configured.parent):

        policy.require_persistent_catalog_activation()
        print("PASS: Simulated activation validates file identity and triggers.")

        try:
            service.import_catalog_csv_persistent(
                actor_id=associate.pk,
                content=CSV_DENIED,
                name="Unauthorized Acceptance 4689",
                description="Disposable file-backed test",
            )
        except PermissionDenied:
            pass
        else:
            stop("Unauthorized associate was allowed to import.")

        if counts() != before or audit_state() != (sequence, digest):
            stop("Unauthorized request created records.")

        print("PASS: Unauthorized associate denied without writes.")

        # Simulate a failure after the first product was audited.
        actual_create = service.create_catalog_product
        calls = [0]

        def reject_second(*, actor_id, catalog_id, fields):
            calls[0] += 1
            if calls[0] == 2:
                raise ValueError("Simulated second-row failure")
            return actual_create(
                actor_id=actor_id,
                catalog_id=catalog_id,
                fields=fields,
            )

        with patch.object(
            service, "create_catalog_product", side_effect=reject_second
        ):
            try:
                service.import_catalog_csv_persistent(
                    actor_id=manager.pk,
                    content=CSV_ROLLBACK,
                    name="Lennox Rollback Acceptance 4689",
                    description="Disposable rollback test",
                )
            except ValueError as exc:
                if "Simulated second-row failure" not in str(exc):
                    raise
            else:
                stop("Simulated partial import unexpectedly succeeded.")

        if calls[0] != 2:
            stop("Rollback fault did not reach the second product.")

        if counts() != before or audit_state() != (sequence, digest):
            stop("Failed import left partial equipment or audit records.")

        print("PASS: Second-row failure rolled back catalog, products and audit.")

        catalog, added = service.import_catalog_csv_persistent(
            actor_id=manager.pk,
            content=CSV_VALID,
            name="Carrier Acceptance 4689",
            description="Disposable file-backed test",
        )

        if added != 2 or catalog.name != "Carrier Acceptance 4689":
            stop("Authorized file-backed import result differs.")

        after = counts()

        expected_increments = {
            "users": 0,
            "projects": 0,
            "equipment": 2,
            "catalogs": 1,
            "memberships": 2,
            "audits": 5,
            "outbox": 5,
        }

        for key, increment in expected_increments.items():
            if after[key] != before[key] + increment:
                stop(f"Unexpected count after import: {key}")

        verify_new_chain(sequence, digest, 5, manager)

        if connection.cursor().execute(
            "PRAGMA foreign_key_check"
        ).fetchone():
            stop("Foreign-key integrity failed after import.")

        print("PASS: Authorized manager imported two products.")
        print("PASS: Five audited events and outbox entries verified.")
        print("PASS: Audit sequence and hash links preserved.")
        print("PASS: Original users, projects and Ruud records preserved.")

    # The override has ended; default-deny must be restored.
    if policy.ACTIVATION_APPROVED is not False:
        stop("Activation lock was not restored.")

    try:
        policy.require_persistent_catalog_activation()
    except RuntimeError as exc:
        if "not activated" not in str(exc).lower():
            raise
    else:
        stop("Activation remained enabled after isolated test.")

    connection.close()

    print("PASS: Import activation lock restored to OFF.")


def main():
    if os.environ.get("GECC_SQLITE_PATH"):
        stop("Unexpected inherited SQLite database override.")

    before_hash = fingerprint(SOURCE)

    with tempfile.TemporaryDirectory(
        prefix="veridian_4689_disposable_"
    ) as temporary:
        copied = Path(temporary) / "dev.sqlite3"

        # SQLite backup produces a consistent snapshot even when the
        # local development server has an open database connection.
        with closing(sqlite3.connect(
            SOURCE.as_uri() + "?mode=ro", uri=True
        )) as original:
            if original.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                stop("Source database integrity check failed.")

            with closing(sqlite3.connect(copied)) as destination:
                original.backup(destination)

        if copied == SOURCE or not copied.exists():
            stop("Disposable database creation failed.")

        os.environ["GECC_DEV"] = "1"
        os.environ["VERIDIAN_ENVIRONMENT"] = "development"
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        os.environ["GECC_SQLITE_PATH"] = str(copied)

        print("PASS: Consistent SQLite snapshot copied to disposable file.")

        exercise_copy()

        with closing(sqlite3.connect(copied)) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                stop("Disposable database failed integrity check.")

        print("PASS: Disposable file-backed database integrity verified.")

    # A running development server could legitimately change SQLite
    # after the snapshot was taken, so do not enforce a stale hash.
    # This process has never opened SOURCE in write mode.
    after_hash = fingerprint(SOURCE)

    print("=== STEP 1907P-4689 FILE-BACKED ACCEPTANCE PASSED ===")
    print("Source SHA256 before:", before_hash)
    print("Source SHA256 after: ", after_hash)
    print("Source database opened: READ ONLY")
    print("Disposable test database: DELETED AFTER SUCCESS")
    print("Persistent import activation in installed code: OFF")
    print("Production activation: NONE")


if __name__ == "__main__":
    main()
