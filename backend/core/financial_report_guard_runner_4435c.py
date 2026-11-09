"""Test-only restoration of original FinancialReport SQLite triggers.

No migration installation, persistent database or PostgreSQL access.
"""

from importlib import import_module

from django.conf import settings
from django.db import connections, migrations

from .completion_guard_runner_4273C import _TestOnlyExecutor
from .payroll_financial_guard_runner_4370 import (
    PayrollFinancialGuardRunner4370,
)


EXPECTED = frozenset({
    "gecc_financial_report_insert_guard",
    "gecc_financial_report_update_guard",
    "gecc_financial_report_delete_guard",
})


class FinancialReportGuardRunner4435C(PayrollFinancialGuardRunner4370):
    def setup_databases(self, **kwargs):
        configured = settings.DATABASES["default"]

        if (
            configured.get("ENGINE") != "django.db.backends.sqlite3"
            or str(configured.get("NAME")) != ":memory:"
            or str(configured.get("TEST", {}).get("NAME")) != ":memory:"
            or settings.MIGRATION_MODULES.get("core", "missing") is not None
        ):
            raise RuntimeError(
                "STOP: Financial report guards require disposable SQLite."
            )

        database_config = super().setup_databases(**kwargs)
        connection = connections["default"]

        if connection.vendor != "sqlite":
            raise RuntimeError("STOP: Unsupported financial test database.")

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA database_list")
            databases = cursor.fetchall()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            )
            before = {row[0] for row in cursor.fetchall()}

        main = [row for row in databases if row[1] == "main"]
        if len(main) != 1 or main[0][2] not in ("", None):
            raise RuntimeError("STOP: Financial test database is persistent.")

        if before & EXPECTED:
            raise RuntimeError(
                "STOP: Financial report triggers already installed."
            )

        migration = import_module(
            "core.migrations.0032_financial_report_safeguards"
        )
        operations = list(migration.Migration.operations)
        installers = [
            operation for operation in operations
            if isinstance(operation, migrations.RunPython)
        ]

        if len(operations) != 1 or len(installers) != 1:
            raise RuntimeError(
                "STOP: Original financial migration structure unexpected."
            )

        installers[0].code(None, _TestOnlyExecutor(connection))

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            )
            after = {row[0] for row in cursor.fetchall()}

        added = after - before
        if added != EXPECTED:
            raise RuntimeError(
                "STOP: Original financial-report trigger inventory mismatch. "
                f"Expected={sorted(EXPECTED)}; actual={sorted(added)}"
            )

        print(
            "PASS: Original three financial-report SQLite triggers "
            "installed in disposable memory."
        )
        return database_config
