"""Read-only preflight for future persistent catalog activation.

This module never writes to databases, applies migrations, imports
equipment, or authorizes database activation.
"""
import hashlib
import json
import sqlite3
from pathlib import Path


EXPECTED_BACKUP_SHA256 = (
    "117f377725040d776c6420de4b0ffeaadd1f99b6c140697de1ad68734b3f4017"
)

EXPECTED_MIGRATION = "0069_employee_compensation_history_integrity"

CATALOG_TABLES = {
    "core_equipmentcatalogitem",
    "core_productcatalogcollection",
    "core_productcatalogmembership",
}

PROTECTED_TABLES = (
    "core_user",
    "core_customer",
    "core_project",
    "core_msr",
    "django_migrations",
)


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_database(path):
    if not path.is_file():
        raise RuntimeError(f"SAFETY STOP: Missing database {path.name}.")

    with sqlite3.connect(
        path.as_uri() + "?mode=ro", uri=True, timeout=10
    ) as db:
        db.execute("PRAGMA query_only=ON")

        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("SAFETY STOP: SQLite integrity failure.")

        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

        if not set(PROTECTED_TABLES).issubset(tables):
            raise RuntimeError(
                "SAFETY STOP: Required historical tables missing."
            )

        migration_names = sorted(
            row[0]
            for row in db.execute(
                "SELECT name FROM django_migrations WHERE app='core'"
            )
        )

        columns = {
            row[1]
            for row in db.execute("PRAGMA table_info('core_project')")
        }

        if "ownership_revision" not in columns:
            raise RuntimeError(
                "SAFETY STOP: Unexpected Project table structure."
            )

        projects = db.execute(
            "SELECT COUNT(*), "
            "COALESCE(SUM(CASE WHEN ownership_revision <> 0 "
            "OR ownership_revision IS NULL THEN 1 ELSE 0 END), 0) "
            "FROM core_project"
        ).fetchone()

        def quoted(name):
            return '"' + name.replace('"', '""') + '"'

        counts = {
            name: db.execute(
                f"SELECT COUNT(*) FROM {quoted(name)}"
            ).fetchone()[0]
            for name in PROTECTED_TABLES
        }

        schema = {
            name: (kind, sql)
            for kind, name, sql in db.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE type IN ('table','index','trigger','view') "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }

        dependent_objects = [
            name
            for name, (kind, sql) in schema.items()
            if kind in ("trigger", "view")
            and sql
            and "ownership_revision" in sql.lower()
        ]

        return {
            "tables": tables,
            "migrations": migration_names,
            "columns": columns,
            "projects": projects,
            "counts": counts,
            "schema": schema,
            "dependent_objects": dependent_objects,
        }


def verify(workspace):
    workspace = Path(workspace).resolve()

    database = workspace / "backend/dev.sqlite3"
    backup = (
        workspace
        / "recovery/step_1907P_4656_pre_catalog_activation.sqlite3"
    )
    manifest_path = (
        workspace
        / "recovery/step_1907P_4656_backup_manifest.json"
    )
    catalog_source = (
        workspace
        / "backend/core/catalog_sources/ruud_2026_20261113.json"
    )

    if not manifest_path.is_file() or not catalog_source.is_file():
        raise RuntimeError(
            "SAFETY STOP: Backup manifest or Ruud source missing."
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ruud = json.loads(catalog_source.read_text(encoding="utf-8"))

    if (
        fingerprint(backup) != EXPECTED_BACKUP_SHA256
        or manifest.get("sha256") != EXPECTED_BACKUP_SHA256
        or manifest.get("integrity_check") != "ok"
    ):
        raise RuntimeError(
            "SAFETY STOP: Recovery backup verification failed."
        )

    if (
        ruud.get("catalog_name") != "Ruud Residential Systems"
        or ruud.get("equipment_count") != 15
        or len(ruud.get("records", [])) != 15
        or len({
            row["ahri_reference"] for row in ruud["records"]
        }) != 15
    ):
        raise RuntimeError(
            "SAFETY STOP: Ruud catalog manifest failed validation."
        )

    original = inspect_database(database)
    saved = inspect_database(backup)

    if original["migrations"] != saved["migrations"]:
        raise RuntimeError(
            "SAFETY STOP: Database migration history changed "
            "since the recovery checkpoint."
        )

    if original["counts"] != saved["counts"]:
        raise RuntimeError(
            "SAFETY STOP: Protected record counts changed "
            "since the recovery checkpoint."
        )

    if original["schema"] != saved["schema"]:
        raise RuntimeError(
            "SAFETY STOP: Database schema changed "
            "since the recovery checkpoint."
        )

    migrations = original["migrations"]

    if len(migrations) != 69 or migrations[-1] != EXPECTED_MIGRATION:
        raise RuntimeError(
            "SAFETY STOP: Unexpected migration baseline."
        )

    if CATALOG_TABLES.intersection(original["tables"]):
        raise RuntimeError(
            "SAFETY STOP: Catalog tables already exist; "
            "activation state requires separate review."
        )

    project_count, invalid_revisions = original["projects"]

    if invalid_revisions:
        raise RuntimeError(
            "SAFETY STOP: Existing ownership revisions "
            "require individual reconciliation."
        )

    if original["dependent_objects"]:
        raise RuntimeError(
            "SAFETY STOP: Ownership revision has dependent schema."
        )

    return {
        "database": "backend/dev.sqlite3",
        "recovery_backup_sha256": EXPECTED_BACKUP_SHA256,
        "applied_core_migrations": len(migrations),
        "existing_projects": project_count,
        "catalog_tables_present": 0,
        "ruud_configurations": 15,
        "historical_schema_and_counts_match_backup": True,
        "read_only_preflight": "PASSED",
        "persistent_activation_authorized": False,
    }


if __name__ == "__main__":
    workspace = Path(__file__).resolve().parents[2]
    result = verify(workspace)

    print("=== PERSISTENT CATALOG ACTIVATION PREFLIGHT ===")
    for key, value in result.items():
        print(f"{key}: {value}")

    print("=== PREFLIGHT PASSED ===")
    print("Database writes: NONE")
    print("Migrations executed: NONE")
    print("Ruud import executed: NO")
    print("Persistent activation: NOT AUTHORIZED")
