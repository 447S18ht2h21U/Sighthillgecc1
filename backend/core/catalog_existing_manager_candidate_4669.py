"""QUARANTINED rehearsal only. Never deploy this database as operational data."""
import hashlib
import json
import os
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import django
django.setup()

from django.conf import settings
from django.core.management import call_command
from django.db import connection

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "recovery/step_1907P_4656_pre_catalog_activation.sqlite3"
TARGET = ROOT / "recovery/step_1907P_4669_QUARANTINED_candidate.sqlite3"
REPORT = ROOT / "recovery/step_1907P_4669_candidate_report.json"
EXPECTED = "117f377725040d776c6420de4b0ffeaadd1f99b6c140697de1ad68734b3f4017"

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1048576), b""):
            h.update(block)
    return h.hexdigest()

def stop(reason):
    raise RuntimeError("SAFETY STOP: " + reason)

if TARGET.exists() or REPORT.exists():
    stop("Candidate or report already exists.")

if digest(SOURCE) != EXPECTED:
    stop("Recovery source fingerprint mismatch.")

if not (
    settings.ENVIRONMENT == "development"
    and connection.vendor == "sqlite"
    and str(connection.settings_dict["NAME"]) == ":memory:"
):
    stop("Only disposable in-memory migration execution permitted.")

connection.ensure_connection()

with sqlite3.connect(SOURCE.as_uri() + "?mode=ro", uri=True) as saved:
    saved.execute("PRAGMA query_only=ON")
    if saved.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        stop("Recovery source integrity failed.")
    saved.backup(connection.connection)

print("PASS: Verified development snapshot restored to memory.", flush=True)

def inventory(db):
    db.row_factory = sqlite3.Row
    tables = {
        row["name"] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    counts = {}
    for table in sorted(tables):
        if table.startswith("sqlite_"):
            continue
        escaped = '"' + table.replace('"', '""') + '"'
        counts[table] = db.execute(
            f"SELECT COUNT(*) AS n FROM {escaped}"
        ).fetchone()["n"]
    return counts

baseline_counts = inventory(connection.connection)
if baseline_counts.get("core_project") != 3:
    stop("Expected three historical projects.")

with connection.cursor() as cursor:
    cursor.execute("PRAGMA table_info('core_project')")
    cols = {row[1] for row in cursor.fetchall()}
    if "ownership_revision" not in cols:
        stop("Expected known Project schema drift.")

    cursor.execute(
        "SELECT COUNT(*) FROM core_project "
        "WHERE ownership_revision IS NULL OR ownership_revision <> 0"
    )
    if cursor.fetchone()[0]:
        stop("Nondefault Project revision requires separate handling.")

    cursor.execute(
        "SELECT type, name FROM sqlite_master "
        "WHERE type IN ('trigger','view') "
        "AND sql LIKE '%ownership_revision%'"
    )
    if cursor.fetchall():
        stop("Ownership revision has dependent schema objects.")

    cursor.execute(
        "SELECT COUNT(*) FROM django_migrations "
        "WHERE app='core' AND name LIKE '0073%'"
    )
    if cursor.fetchone()[0]:
        stop("Migration 0073 already recorded.")

    cursor.execute(
        'ALTER TABLE "core_project" DROP COLUMN "ownership_revision"'
    )

print("PASS: Known schema drift reconciled in disposable memory.", flush=True)

# Disable Django's SQLite SQL-debug formatter during migrations only.
# Migration identity and authorization guards remain fully enforced.
debug_before = settings.DEBUG
force_debug_before = connection.force_debug_cursor
try:
    settings.DEBUG = False
    connection.force_debug_cursor = False
    call_command(
        "migrate", "core", "0082_completion_attempt_send_lifecycle",
        interactive=False, verbosity=1,
    )
finally:
    # Keep SQLite SQL-debug formatting disabled for subsequent ORM
    # operations in this disposable process, including Ruud import.
    settings.DEBUG = False
    connection.force_debug_cursor = False

with connection.cursor() as cursor:
    cursor.execute(
        "SELECT COUNT(*) FROM django_migrations WHERE app='core'"
    )
    if cursor.fetchone()[0] != 82:
        stop("Full migration sequence incomplete.")

for table in ("core_customer", "core_project", "core_msr"):
    current = inventory(connection.connection).get(table)
    if current != baseline_counts.get(table):
        stop(f"Historical count changed: {table}")

from core.models import (
    AuditEvent, AuditHead, EquipmentCatalogItem,
    ProductCatalogMembership, Role, User,
)
from core.ruud_catalog_import_service_4650 import import_ruud_catalog

AuditHead.objects.get_or_create(pk=1)
# Reuse an existing active manager; never create a rehearsal user.
actor = User.objects.filter(
    is_active=True,
    role__in=(Role.SALES_MANAGER, Role.INSTALLATION_MANAGER),
).order_by("pk").first()
if actor is None:
    stop("No active catalog manager exists in restored database.")

catalog, added = import_ruud_catalog(actor_id=actor.pk)
repeat, repeated = import_ruud_catalog(actor_id=actor.pk)

if added != 15 or repeated != 0 or repeat.pk != catalog.pk:
    stop("Ruud import did not meet count or idempotency requirements.")

if EquipmentCatalogItem.objects.filter(
    brand="Ruud", is_active=True
).count() != 15:
    stop("Ruud equipment count mismatch.")

if ProductCatalogMembership.objects.filter(
    catalog=catalog
).count() != 15:
    stop("Ruud membership count mismatch.")

for action, expected_count in (
    ("equipment.catalog.created", 15),
    ("product.catalog.membership.created", 15),
    ("product.catalog.collection.created", 1),
):
    if AuditEvent.objects.filter(action=action).count() != expected_count:
        stop(f"Audit action count mismatch: {action}")

# Existing identities and historical audit events must remain intact.
if inventory(connection.connection).get("core_user") != baseline_counts.get("core_user"):
    stop("Import unexpectedly changed user count.")

with connection.cursor() as cursor:
    cursor.execute("SELECT sequence, digest FROM core_audithead WHERE id=1")
    head_sequence, head_digest = cursor.fetchone()

    cursor.execute(
        "SELECT sequence, previous_hash, digest, actor_id "
        "FROM core_auditevent ORDER BY sequence"
    )
    chain = cursor.fetchall()

if len(chain) < 31 or len({r[0] for r in chain}) != len(chain):
    stop("Audit-chain sequence is incomplete or duplicated.")

new_events = chain[-31:]
prior_digest = chain[-32][2] if len(chain) > 31 else None

for sequence, previous_hash, digest, actor_id in new_events:
    if prior_digest is not None and previous_hash != prior_digest:
        stop("New audit event does not link to its predecessor.")
    if not digest or actor_id != actor.pk.hex:
        stop("Ruud audit attribution differs from selected manager.")
    prior_digest = digest

if head_sequence != new_events[-1][0] or head_digest != prior_digest:
    stop("Audit head does not match final Ruud event.")

if new_events[-1][0] - new_events[0][0] != 30:
    stop("Ruud audit sequence is not contiguous.")

with connection.cursor() as cursor:
    cursor.execute(
        "SELECT COUNT(*) FROM core_outbox "
        "WHERE event_id IN ("
        "SELECT id FROM core_auditevent WHERE sequence BETWEEN ? AND ?)",
        (new_events[0][0], new_events[-1][0]),
    )
    if cursor.fetchone()[0] != 31:
        stop("Audit outbox does not contain all 31 Ruud events.")

print("PASS: Existing user count preserved.")
print("PASS: All 31 events attributed to existing manager.")
print("PASS: Audit sequence, hash links, head and outbox verified.")
print("PASS: 15 Ruud systems and 31 audit events verified.", flush=True)

# Export the migrated in-memory image to a separate, quarantined file.
# This is NOT an installation of migrations against file-backed SQLite.
with TARGET.open("xb"):
    pass

with sqlite3.connect(TARGET) as destination:
    connection.connection.backup(destination)

with sqlite3.connect(TARGET.as_uri() + "?mode=ro", uri=True) as db:
    db.execute("PRAGMA query_only=ON")

    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        stop("File-backed candidate integrity check failed.")

    candidate_counts = inventory(db)
    memory_counts = inventory(connection.connection)

    if candidate_counts != memory_counts:
        stop("File-backed export record counts differ.")

    triggers = {
        name: sql or ""
        for name, sql in db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='trigger'"
        )
    }

    required_equipment = {
        "equipment_history_update_guard",
        "equipment_history_delete_guard",
    }
    equipment_present = required_equipment.issubset(triggers)

    delegation_triggers = sorted(
        name for name in triggers
        if "delegation" in name.lower()
        or "msr_evidence" in name.lower()
    )

    finance_triggers = sorted(
        name for name, sql in triggers.items()
        if "financialreport" in sql.lower()
        or "financial_report" in sql.lower()
    )

    core_migrations = db.execute(
        "SELECT COUNT(*) FROM django_migrations WHERE app='core'"
    ).fetchone()[0]

if core_migrations != 82 or not equipment_present:
    stop("Candidate migration history or equipment guards incomplete.")

if digest(SOURCE) != EXPECTED:
    stop("Recovery backup changed.")

warnings = [
    "TEST-ONLY migration pathway was used in memory.",
    "Candidate is QUARANTINED and must never replace dev.sqlite3.",
    "SQLite financial-report guard coverage requires separate review.",
    "MSR delegation evidence guard coverage requires separate review.",
    "Persistent activation still requires independent authorization.",
]

result = {
    "checkpoint": "1907P-4669",
    "classification": "QUARANTINED_REHEARSAL_NOT_DEPLOYABLE",
    "candidate": str(TARGET.relative_to(ROOT)),
    "candidate_sha256": digest(TARGET),
    "candidate_bytes": TARGET.stat().st_size,
    "core_migrations": core_migrations,
    "ruud_systems": 15,
    "ruud_audit_events": 31,
    "equipment_guards_present": sorted(required_equipment),
    "delegation_trigger_names": delegation_triggers,
    "financial_trigger_names": finance_triggers,
    "all_table_counts_match_export": True,
    "source_backup_sha256": EXPECTED,
    "warnings": warnings,
    "persistent_activation_authorized": False,
}

with REPORT.open("x", encoding="utf-8") as output:
    json.dump(result, output, indent=2)
    output.write("\n")

print("\n=== QUARANTINED FILE-BACKED CANDIDATE ===")
print("PASS: SQLite file integrity verified.")
print("PASS: All table record counts match in-memory source.")
print("PASS: Equipment historical-update and deletion guards exist.")
print("Core migrations:", core_migrations)
print("Financial-related trigger names:", finance_triggers)
print("Delegation-related trigger names:", delegation_triggers)
print("Candidate SHA256:", result["candidate_sha256"])
print("Candidate file:", result["candidate"])
print("Report:", REPORT.relative_to(ROOT))
print("CLASSIFICATION: QUARANTINED - NOT DEPLOYABLE")
print("Persistent database activation: NOT AUTHORIZED")
