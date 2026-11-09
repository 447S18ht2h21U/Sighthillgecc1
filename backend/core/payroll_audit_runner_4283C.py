"""Payroll-only test runner extending verified completion guard isolation.

Never used for operational databases, migrations, or live payment access.
"""
from django.db import connections

from .completion_guard_runner_4273C import CompletionGuardRunner


class PayrollAuditRunner4283C(CompletionGuardRunner):
    def setup_databases(self, **kwargs):
        # The protected parent validates settings BEFORE test DB creation,
        # proves the runtime SQLite database is memory-only, and installs
        # the four original completion-envelope triggers.
        database_config = super().setup_databases(**kwargs)

        connection = connections["default"]

        if connection.vendor != "sqlite":
            raise RuntimeError("STOP: Payroll tests prohibit PostgreSQL.")

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA database_list")
            databases = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) FROM core_audithead")
            head_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM core_auditevent")
            event_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM core_outbox")
            outbox_count = cursor.fetchone()[0]

        main = [row for row in databases if row[1] == "main"]

        if len(main) != 1 or main[0][2] not in ("", None):
            raise RuntimeError(
                "STOP: Payroll test database has a persistent file path."
            )

        if head_count or event_count or outbox_count:
            raise RuntimeError(
                "STOP: Payroll test audit tables are not initially empty."
            )

        from .models import AuditHead

        # Original model defaults, matching migration 0002 genesis.
        head = AuditHead.objects.create(pk=1)

        if (
            head.pk != 1
            or head.sequence != 0
            or head.digest != "0" * 64
            or AuditHead.objects.count() != 1
        ):
            raise RuntimeError(
                "STOP: Audit-chain genesis failed verification."
            )

        print(
            "PASS: Original audit genesis initialized "
            "in disposable SQLite memory."
        )
        print(
            "PASS: Financial audit recording and outbox remain active."
        )
        return database_config