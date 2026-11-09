"""Experimental SQLite append-only guards for five MSR evidence tables.

NOT installed by migrations or runtime services. PostgreSQL protection,
atomic auditing and approved authorization are still required.
"""
from django.core.exceptions import ImproperlyConfigured

EVIDENCE_TABLES = (
    "core_msrdelegationrequest",
    "core_msrdelegationrequestproject",
    "core_msrdelegationdecision",
    "core_msrdelegationtermination",
    "core_msrdelegationprojectinvalidation",
)


def install_isolated_evidence_guards(connection):
    """Create immutable-evidence triggers ONLY on disposable SQLite memory."""
    if connection.vendor != "sqlite":
        raise ImproperlyConfigured("SAFETY STOP: SQLite guard requires SQLite")
    name = str(connection.settings_dict.get("NAME", ""))
    if name not in (
        ":memory:",
        "file:memorydb_default?mode=memory&cache=shared",
    ):
        raise ImproperlyConfigured("SAFETY STOP: Persistent SQLite denied")

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA database_list")
        databases = cursor.fetchall()
        if any(row[2] for row in databases if row[1] == "main"):
            raise ImproperlyConfigured("SAFETY STOP: Database is on disk")
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
        present = {row[0] for row in cursor.fetchall()}
        if not set(EVIDENCE_TABLES).issubset(present):
            raise ImproperlyConfigured(
                "SAFETY STOP: Missing delegation evidence tables"
            )

        for table in EVIDENCE_TABLES:
            for action in ("UPDATE", "DELETE"):
                trigger = f"msr_immutable_{table}_{action.lower()}"
                sql = (
                    f'CREATE TRIGGER IF NOT EXISTS "{trigger}" '
                    f'BEFORE {action} ON "{table}" '
                    "BEGIN SELECT RAISE(ABORT, "
                    "'MSR delegation evidence is immutable'); END"
                )
                cursor.execute(sql)

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        )
        actual = {row[0] for row in cursor.fetchall()}
        expected = {
            f"msr_immutable_{table}_{action}"
            for table in EVIDENCE_TABLES
            for action in ("update", "delete")
        }
        if not expected.issubset(actual):
            raise RuntimeError("SAFETY STOP: Evidence triggers missing")
    return len(expected)