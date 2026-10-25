"""Use execution time for PostgreSQL temporary project-access approval checks."""

from django.db import migrations


FUNCTION_NAME = "gecc_temporary_project_access_approval_authority()"
OLD_EXPRESSION = "CURRENT_TIMESTAMP"
NEW_EXPRESSION = "clock_timestamp()"
EXPECTED_REFERENCES = 4


def replace_time_expression(schema_editor, *, old, new):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_functiondef(%s::regprocedure)",
            [FUNCTION_NAME],
        )
        row = cursor.fetchone()

    if row is None or not row[0]:
        raise RuntimeError(
            "SAFETY STOP: Project-access approval function is missing."
        )

    definition = row[0]

    if definition.count(old) != EXPECTED_REFERENCES:
        raise RuntimeError(
            "SAFETY STOP: Unexpected project-access timestamp expressions."
        )

    if new in definition:
        raise RuntimeError(
            "SAFETY STOP: Project-access function has mixed timestamp rules."
        )

    updated = definition.replace(old, new)

    if updated.count(new) != EXPECTED_REFERENCES:
        raise RuntimeError(
            "SAFETY STOP: Timestamp replacement validation failed."
        )

    schema_editor.execute(updated)


def install(apps, schema_editor):
    replace_time_expression(
        schema_editor,
        old=OLD_EXPRESSION,
        new=NEW_EXPRESSION,
    )


def uninstall(apps, schema_editor):
    replace_time_expression(
        schema_editor,
        old=NEW_EXPRESSION,
        new=OLD_EXPRESSION,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0059_postgresql_employee_payroll_integrity"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]