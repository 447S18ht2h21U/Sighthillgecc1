"""Test-only audit genesis for the existing protected completion runner.

Operational databases, migrations, and audit services remain unchanged.
"""
from django.db import connections

from .completion_guard_runner_4273C import CompletionGuardRunner


class PayrollAuditRunner4283B(CompletionGuardRunner):
    def setup_databases(self, **kwargs):
        # Parent performs strict in-memory database checks and installs
        # the original, unchanged completion-envelope SQLite guards.
        database_config = super().setup_databases(**kwargs)

        from django.conf import settings

        configured = settings.DATABASES["default"]
        connection = connections["default"]

        if (
            configured["ENGINE"] != "django.db.backends.sqlite3"
            or configured.get("NAME") != ":memory:"
            or configured.get("TEST", {}).get("NAME") != ":memory:"
            or settings.MIGRATION_MODULES.get("core", "missing") is not None
            or connection.vendor != "sqlite"
        ):
            raise RuntimeError(
                "STOP: Payroll audit genesis requires disposable in-memory SQLite."
            )

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA database_list")
            databases = cursor.fetchall()
            cursor.execute(
                "SELECT COUNT(*) FROM core_audithead"
            )
            head_count = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM core_auditevent"
            )
            event_count = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM core_outbox"
            )
            outbox_count = cursor.fetchone()[0]

        main = [row for row in databases if row[1] == "main"]
        if len(main) != 1 or main[0][2] not in ("", None):
            raise RuntimeError("STOP: Unexpected persistent database location.")

        if head_count or event_count or outbox_count:
            raise RuntimeError(
                "STOP: Audit tables not empty before test-only initialization."
            )

        from .models import AuditHead

        # Exact genesis defaults declared in the original AuditHead model.
        genesis = AuditHead.objects.create(pk=1)

        if (
            genesis.pk != 1
            or genesis.sequence != 0
            or genesis.digest != "0" * 64
            or AuditHead.objects.count() != 1
        ):
            raise RuntimeError(
                "STOP: Original audit-chain genesis verification failed."
            )

        print(
            "PASS: Original AuditHead genesis initialized "
            "in disposable in-memory SQLite."
        )
        print(
            "PASS: Full audit-event and outbox recording retained; "
            "nothing mocked or bypassed."
        )
        return database_config