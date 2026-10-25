"""Protect approved contractor payment financial fields in PostgreSQL."""

from django.db import migrations


FUNCTION_NAME = "gecc_contractor_payment_guard()"

PROTECTION_MESSAGE = "Approved contractor payments cannot change"

PROTECTED_FIELDS = (
    "engagement_id",
    "compensation_plan_id",
    "project_id",
    "kind",
    "basis_amount",
    "deduction_amount",
    "final_amount",
    "calculation_snapshot",
)

APPROVED_GUARD = """
                    IF OLD.status = 'APPROVED'
                       AND (
                           NEW.engagement_id IS DISTINCT FROM OLD.engagement_id
                           OR NEW.compensation_plan_id IS DISTINCT FROM OLD.compensation_plan_id
                           OR NEW.project_id IS DISTINCT FROM OLD.project_id
                           OR NEW.kind IS DISTINCT FROM OLD.kind
                           OR NEW.basis_amount IS DISTINCT FROM OLD.basis_amount
                           OR NEW.deduction_amount IS DISTINCT FROM OLD.deduction_amount
                           OR NEW.final_amount IS DISTINCT FROM OLD.final_amount
                           OR NEW.calculation_snapshot IS DISTINCT FROM OLD.calculation_snapshot
                       ) THEN
                        RAISE EXCEPTION
                        'Approved contractor payments cannot change';
                    END IF;
"""

OLD_GUARD = """                    IF OLD.status = 'PAID' THEN
                        RAISE EXCEPTION
                        'Paid contractor payments are immutable';
                    END IF;"""

NEW_GUARD = OLD_GUARD + "\n" + APPROVED_GUARD


def replace_guard(schema_editor, old, new):
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
            "SAFETY STOP: Contractor payment function missing."
        )

    definition = row[0]

    if definition.count(old) != 1:
        raise RuntimeError(
            "SAFETY STOP: Unexpected contractor payment function structure."
        )

    if old == OLD_GUARD and PROTECTION_MESSAGE in definition:
        raise RuntimeError(
            "SAFETY STOP: Approved-payment protection already exists."
        )

    updated = definition.replace(old, new, 1)

    if updated == definition:
        raise RuntimeError("SAFETY STOP: No database change prepared.")

    schema_editor.execute(updated)


def install(apps, schema_editor):
    replace_guard(
        schema_editor,
        OLD_GUARD,
        NEW_GUARD,
    )


def uninstall(apps, schema_editor):
    replace_guard(
        schema_editor,
        NEW_GUARD,
        OLD_GUARD,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0060_postgresql_project_access_transaction_time"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]
