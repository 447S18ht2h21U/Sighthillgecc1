"""Test-only installation of EXISTING SQLite completion-envelope guards.

Never targets a file database or the operational PostgreSQL environment.
Does not modify or apply Django migration files.
"""
from importlib import import_module

from django.db import connections
from django.test.runner import DiscoverRunner


EXPECTED_TRIGGERS = frozenset({
    "gecc_completion_attempt_delete_guard",
    "gecc_completion_attempt_identity_guard",
    "gecc_completion_attempt_lifecycle_guard",
    "gecc_completion_attempt_initial_guard",
})


class _TestOnlyExecutor:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement):
        with self.connection.cursor() as cursor:
            cursor.execute(statement)


class CompletionGuardRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        # Check the unmodified test settings BEFORE any database setup.
        from django.conf import settings
        configured = settings.DATABASES["default"]

        if (
            configured["ENGINE"] != "django.db.backends.sqlite3"
            or configured.get("NAME") != ":memory:"
            or configured.get("TEST", {}).get("NAME") != ":memory:"
            or settings.MIGRATION_MODULES.get("core", "missing") is not None
        ):
            raise RuntimeError(
                "STOP: Only the existing disposable SQLite test "
                "configuration may use this runner."
            )

        database_config = super().setup_databases(**kwargs)

        connection = connections["default"]

        if connection.vendor != "sqlite":
            raise RuntimeError("STOP: PostgreSQL is prohibited.")

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA database_list")
            databases = cursor.fetchall()

        # SQLite memory databases have no filesystem path.
        main = [row for row in databases if row[1] == "main"]
        if len(main) != 1 or main[0][2] not in ("", None):
            raise RuntimeError(
                "STOP: The test database is not an in-memory database."
            )

        runtime_name = str(connection.settings_dict["NAME"])

        if not (
            runtime_name == ":memory:"
            or (
                runtime_name.startswith("file:memorydb_")
                and "mode=memory" in runtime_name
                and "cache=shared" in runtime_name
            )
        ):
            raise RuntimeError(
                "STOP: Unexpected SQLite runtime database identity."
            )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' "
                "AND name='core_completionenvelopeattempt'"
            )
            if cursor.fetchone() is None:
                raise RuntimeError(
                    "STOP: Disposable completion-envelope table missing."
                )

            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='trigger' AND name LIKE "
                "'gecc_completion_attempt_%'"
            )
            existing = {row[0] for row in cursor.fetchall()}

        if existing:
            raise RuntimeError(
                "STOP: Completion triggers already present; "
                "refusing to overwrite or duplicate them."
            )

        schema = _TestOnlyExecutor(connection)

        m57 = import_module(
            "core.migrations.0057_completion_envelope_attempt"
        )
        m58 = import_module(
            "core.migrations.0058_completion_envelope_identity_guards"
        )

        # These are exact, unmodified SQLite migration guard functions.
        m57.install_guards(None, schema)
        m58.install_sqlite_identity_guard(None, schema)
        m58.install_sqlite_lifecycle_guard(None, schema)
        m58.install_sqlite_initial_guard(None, schema)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='trigger' AND name LIKE "
                "'gecc_completion_attempt_%'"
            )
            actual = {row[0] for row in cursor.fetchall()}

        if actual != EXPECTED_TRIGGERS:
            raise RuntimeError(
                "STOP: Exact four-trigger installation verification failed. "
                f"Expected {sorted(EXPECTED_TRIGGERS)}, "
                f"found {sorted(actual)}."
            )

        print(
            "PASS: Four original completion-envelope SQLite "
            "triggers installed in disposable memory."
        )
        print(
            "PASS: Core migrations and operational databases untouched."
        )

        return database_config