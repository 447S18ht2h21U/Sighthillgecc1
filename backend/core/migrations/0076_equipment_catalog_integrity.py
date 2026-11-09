"""Test-only database protection for historical equipment records.

Not authorized for persistent databases. Production PostgreSQL protection
requires its own reviewed migration before catalog activation.
"""

import os

from django.db import migrations


def install_test_guards(apps, schema_editor):
    connection = schema_editor.connection
    name = str(connection.settings_dict.get("NAME", ""))
    if (
        connection.vendor != "sqlite"
        or name not in (
            ":memory:",
            "file:memorydb_default?mode=memory&cache=shared",
        )
        or os.environ.get("VERIDIAN_0076_TEST_INSTALL")
        != "ISOLATED_SQLITE_MEMORY"
    ):
        raise RuntimeError(
            "SAFETY STOP: Migration 0076 requires authorized "
            "disposable in-memory SQLite."
        )

    table = apps.get_model("core", "EquipmentCatalogItem")._meta.db_table
    if table != "core_equipmentcatalogitem":
        raise RuntimeError("SAFETY STOP: Unexpected equipment table.")

    statements = [
        """
        CREATE TRIGGER equipment_history_update_guard
        BEFORE UPDATE ON core_equipmentcatalogitem
        WHEN
            NEW.brand IS NOT OLD.brand OR
            NEW.residential_system_type IS NOT OLD.residential_system_type OR
            NEW.model_number IS NOT OLD.model_number OR
            NEW.description IS NOT OLD.description OR
            NEW.revision IS NOT OLD.revision OR
            NEW.supersedes_id IS NOT OLD.supersedes_id OR
            NEW.created_by_id IS NOT OLD.created_by_id OR
            (OLD.is_active = 0 AND NEW.is_active <> 0)
        BEGIN
            SELECT RAISE(ABORT, 'Equipment history is immutable');
        END;
        """,
        """
        CREATE TRIGGER equipment_history_delete_guard
        BEFORE DELETE ON core_equipmentcatalogitem
        BEGIN
            SELECT RAISE(ABORT, 'Equipment history cannot be deleted');
        END;
        """,
    ]

    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)
        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='trigger' AND name LIKE 'equipment_history_%_guard'"
        )
        installed = {row[0] for row in cursor.fetchall()}

    if installed != {
        "equipment_history_update_guard",
        "equipment_history_delete_guard",
    }:
        raise RuntimeError("SAFETY STOP: Equipment triggers incomplete.")


def refuse_reverse(apps, schema_editor):
    raise RuntimeError(
        "SAFETY STOP: Automatic equipment guard removal prohibited."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0075_equipment_catalog_foundation"),
    ]

    operations = [
        migrations.RunPython(install_test_guards, refuse_reverse),
    ]