"""Test-only recovery of ORIGINAL SQLite payroll financial safeguards.

Never installs Django migrations or targets a persistent database.
Original migration install functions run only after disposable SQLite
and audit genesis are verified by the existing protected parent runner.
"""

from importlib import import_module

from django.conf import settings
from django.db import connections

from .completion_guard_runner_4273C import _TestOnlyExecutor
from .payroll_audit_runner_4283C import PayrollAuditRunner4283C


FINANCIAL_MIGRATIONS = (
    "core.migrations.0028_employee_payroll_safeguards",
    "core.migrations.0068_employee_payroll_compensation_relationship_guards",
    "core.migrations.0069_employee_compensation_history_integrity",
    "core.migrations.0071_contractor_payment_evidence_safeguards",
)

EXPECTED_TRIGGERS = frozenset({
    "gecc_employee_comp_plan_update_guard",
    "gecc_employee_payroll_insert_guard",
    "gecc_employee_payroll_update_guard",
    "gecc_employee_payroll_delete_guard",
    "gecc_payroll_plan_relationship_insert",
    "gecc_payroll_plan_relationship_update",
    "gecc_employee_comp_approved_delete_guard",
    "gecc_contractor_issuance_insert_guard",
    "gecc_contractor_issuance_update_guard",
    "gecc_contractor_issuance_delete_guard",
    "gecc_contractor_settlement_insert_guard",
    "gecc_contractor_settlement_update_guard",
    "gecc_contractor_settlement_delete_guard",
    "gecc_contractor_verified_paid_guard",
})

EXPECTED_INDEX = "gecc_employee_comp_approved_date_uq"


class PayrollFinancialGuardRunner4370(PayrollAuditRunner4283C):
    def setup_databases(self, **kwargs):
        configured = settings.DATABASES["default"]

        if (
            configured.get("ENGINE") != "django.db.backends.sqlite3"
            or configured.get("NAME") != ":memory:"
            or configured.get("TEST", {}).get("NAME") != ":memory:"
            or settings.MIGRATION_MODULES.get("core", "missing") is not None
        ):
            raise RuntimeError(
                "STOP: Financial guard recovery requires disposable "
                "in-memory SQLite with core migrations disabled."
            )

        # The existing parent checks the runtime memory database,
        # installs completion guards and initializes audit genesis.
        database_config = super().setup_databases(**kwargs)

        connection = connections["default"]

        if connection.vendor != "sqlite":
            raise RuntimeError("STOP: PostgreSQL financial setup forbidden.")

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA database_list")
            database_rows = cursor.fetchall()

            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'trigger'"
            )
            before_triggers = {row[0] for row in cursor.fetchall()}

            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'index'"
            )
            before_indexes = {row[0] for row in cursor.fetchall()}

        main = [row for row in database_rows if row[1] == "main"]

        if len(main) != 1 or main[0][2] not in ("", None):
            raise RuntimeError(
                "STOP: Financial test database has a filesystem path."
            )

        if before_triggers & EXPECTED_TRIGGERS:
            raise RuntimeError(
                "STOP: Financial triggers already exist; no overwrite."
            )

        if EXPECTED_INDEX in before_indexes:
            raise RuntimeError(
                "STOP: Financial index already exists; no overwrite."
            )

        schema = _TestOnlyExecutor(connection)

        for name in FINANCIAL_MIGRATIONS:
            migration = import_module(name)

            if name.endswith("0071_contractor_payment_evidence_safeguards"):
                import os

                # The original migration requires this exact test-only
                # authorization in addition to its database identity check.
                # Refuse to replace a conflicting process authorization.
                key = "VERIDIAN_0071_TEST_INSTALL"
                previous = os.environ.get(key)

                if previous not in (None, "", "ISOLATED_SQLITE_MEMORY"):
                    raise RuntimeError(
                        "STOP: Conflicting financial migration authorization."
                    )

                try:
                    os.environ[key] = "ISOLATED_SQLITE_MEMORY"
                    migration.install(None, schema)
                finally:
                    if previous is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = previous
            else:
                migration.install(None, schema)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'trigger'"
            )
            after_triggers = {row[0] for row in cursor.fetchall()}

            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'index'"
            )
            after_indexes = {row[0] for row in cursor.fetchall()}

        added = after_triggers - before_triggers

        if added != EXPECTED_TRIGGERS:
            raise RuntimeError(
                "STOP: Original financial trigger inventory mismatch. "
                f"Missing={sorted(EXPECTED_TRIGGERS - added)}, "
                f"unexpected={sorted(added - EXPECTED_TRIGGERS)}"
            )

        if EXPECTED_INDEX not in (
            after_indexes - before_indexes
        ):
            raise RuntimeError(
                "STOP: Approved compensation effective-date index missing."
            )

        print(
            "PASS: Original 14 financial SQLite triggers "
            "installed in disposable memory."
        )
        print(
            "PASS: Original approved compensation date index verified."
        )
        print(
            "PASS: Protected completion guards and audit genesis preserved."
        )
        print(
            "PASS: Operational databases and migration files untouched."
        )

        return database_config