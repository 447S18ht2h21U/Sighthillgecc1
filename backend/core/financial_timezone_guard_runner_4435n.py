"""Test-only Eastern-date reconciliation for original SQLite financial guards.

This runner never changes historical migrations, operational databases,
or PostgreSQL. Only a verified disposable in-memory test database
receives the timezone-normalized trigger comparisons.
"""

from django.conf import settings
from django.db import connections, transaction

from .financial_report_guard_runner_4435c import (
    FinancialReportGuardRunner4435C,
)


class FinancialTimezoneGuardRunner4435N(FinancialReportGuardRunner4435C):
    def setup_databases(self, **kwargs):
        configured = settings.DATABASES["default"]

        if (
            configured.get("ENGINE") != "django.db.backends.sqlite3"
            or configured.get("NAME") != ":memory:"
            or configured.get("TEST", {}).get("NAME") != ":memory:"
            or settings.MIGRATION_MODULES.get("core", "missing") is not None
        ):
            raise RuntimeError("STOP: Disposable test SQLite required.")

        result = super().setup_databases(**kwargs)
        connection = connections["default"]

        if connection.vendor != "sqlite":
            raise RuntimeError("STOP: PostgreSQL is prohibited.")

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA database_list")
            main = [
                row for row in cursor.fetchall()
                if row[1] == "main"
            ]

            if len(main) != 1 or main[0][2] not in ("", None):
                raise RuntimeError("STOP: Persistent database prohibited.")

        targets = {
            "gecc_contractor_settlement_insert_guard": (
                ("DATE(i.issued_at)", 1),
                ("DATE(NEW.verified_at)", 1),
            ),
            "gecc_contractor_verified_paid_guard": (
                ("DATE(i.issued_at)", 1),
                ("DATE(s.verified_at)", 1),
            ),
        }

        replacement_dates = {
            "DATE(i.issued_at)": (
                "django_datetime_cast_date("
                "i.issued_at, 'America/New_York', 'UTC')"
            ),
            "DATE(NEW.verified_at)": (
                "django_datetime_cast_date("
                "NEW.verified_at, 'America/New_York', 'UTC')"
            ),
            "DATE(s.verified_at)": (
                "django_datetime_cast_date("
                "s.verified_at, 'America/New_York', 'UTC')"
            ),
        }

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type = 'trigger' AND name IN (?, ?)",
                list(targets),
            )
            originals = dict(cursor.fetchall())

        if set(originals) != set(targets):
            raise RuntimeError("STOP: Original settlement triggers missing.")

        replacements = {}

        for name, required in targets.items():
            original = originals[name]

            if not original or not original.startswith("CREATE TRIGGER "):
                raise RuntimeError("STOP: Unexpected trigger definition.")

            updated = original

            for old, expected_count in required:
                if updated.count(old) != expected_count:
                    raise RuntimeError(
                        "STOP: Trigger comparison inventory changed: "
                        + name + " / " + old
                    )
                updated = updated.replace(old, replacement_dates[old])

            if updated == original:
                raise RuntimeError("STOP: No timezone adjustment applied.")

            replacements[name] = updated

        with transaction.atomic(using="default"):
            with connection.cursor() as cursor:
                for name, sql in replacements.items():
                    cursor.execute('DROP TRIGGER "' + name + '"')
                    cursor.execute(sql)

                cursor.execute(
                    "SELECT name, sql FROM sqlite_master "
                    "WHERE type = 'trigger' AND name IN (?, ?)",
                    list(targets),
                )
                installed = dict(cursor.fetchall())

                if installed != replacements:
                    raise RuntimeError(
                        "STOP: Corrected trigger verification failed."
                    )

        print(
            "PASS: Two original financial settlement triggers "
            "timezone-normalized in disposable memory."
        )
        print(
            "PASS: Independent approval, amounts, timestamps, "
            "and immutable evidence conditions retained."
        )
        print(
            "PASS: Original migration 0071 and operational "
            "database triggers unchanged."
        )
        return result
