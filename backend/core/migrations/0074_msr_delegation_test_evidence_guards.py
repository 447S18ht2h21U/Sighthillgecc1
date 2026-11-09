"""Isolated SQLite test-only installation of MSR immutable-evidence guards.

Never install on persistent SQLite or PostgreSQL. This migration is
intentionally non-reversible and requires an explicit test authorization.
"""

import os

from django.db import migrations

from core.msr_delegation_sqlite_guards import (
    install_isolated_evidence_guards,
)


def install_test_guards(apps, schema_editor):
    connection = schema_editor.connection
    name = str(connection.settings_dict.get("NAME", ""))

    if (
        connection.vendor != "sqlite"
        or name not in (
            ":memory:",
            "file:memorydb_default?mode=memory&cache=shared",
        )
        or os.environ.get("VERIDIAN_0074_TEST_INSTALL")
        != "ISOLATED_SQLITE_MEMORY"
    ):
        raise RuntimeError(
            "SAFETY STOP: MSR delegation evidence migration 0074 "
            "requires authorized disposable in-memory SQLite."
        )

    installed = install_isolated_evidence_guards(connection)
    if installed != 10:
        raise RuntimeError(
            "SAFETY STOP: Expected ten immutable-evidence triggers."
        )


def refuse_reverse(apps, schema_editor):
    raise RuntimeError(
        "SAFETY STOP: Automatic removal of MSR evidence guards prohibited."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0073_msr_delegation_persistence_foundation"),
    ]

    operations = [
        migrations.RunPython(install_test_guards, refuse_reverse),
    ]