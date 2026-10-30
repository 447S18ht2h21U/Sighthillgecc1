"""Preserve approved employee compensation history.

Additive, forward-only database safeguards. Approved plans cannot be
deleted, and approved effective dates must be unique per employee.
Existing approved-plan update triggers remain unchanged.
"""

from django.db import migrations


INDEX_NAME = "gecc_employee_comp_approved_date_uq"


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor not in ("sqlite", "postgresql"):
        raise RuntimeError(
            "SAFETY STOP: Unsupported compensation database vendor."
        )

    # Fail before making schema changes if existing data conflicts.
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT employee_id, effective_date, COUNT(*)
            FROM core_employeecompensationplan
            WHERE status = 'APPROVED'
            GROUP BY employee_id, effective_date
            HAVING COUNT(*) > 1
            """
        )
        if cursor.fetchone() is not None:
            raise RuntimeError(
                "SAFETY STOP: Duplicate approved compensation dates exist."
            )

    # The unique partial index also protects against concurrent approvals.
    schema_editor.execute(
        f"""
        CREATE UNIQUE INDEX {INDEX_NAME}
        ON core_employeecompensationplan (
            employee_id, effective_date
        )
        WHERE status = 'APPROVED'
        """
    )

    if vendor == "sqlite":
        schema_editor.execute(
            """
            CREATE TRIGGER gecc_employee_comp_approved_delete_guard
            BEFORE DELETE ON core_employeecompensationplan
            WHEN OLD.status = 'APPROVED'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Approved employee compensation history cannot be deleted'
                );
            END
            """
        )

    elif vendor == "postgresql":
        schema_editor.execute(
            """
            CREATE FUNCTION gecc_employee_comp_approved_delete_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.status = 'APPROVED' THEN
                    RAISE EXCEPTION
                        'Approved employee compensation history cannot be deleted';
                END IF;
                RETURN OLD;
            END $$;
            """
        )
        schema_editor.execute(
            """
            CREATE TRIGGER gecc_employee_comp_approved_delete_guard
            BEFORE DELETE ON core_employeecompensationplan
            FOR EACH ROW
            EXECUTE FUNCTION gecc_employee_comp_approved_delete_guard();
            """
        )


def uninstall(apps, schema_editor):
    # Never silently remove compensation history protections.
    raise RuntimeError(
        "SAFETY STOP: Compensation history safeguards require "
        "a separately reviewed rollback migration."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0068_employee_payroll_compensation_relationship_guards"),
    ]

    operations = [
        migrations.RunPython(install, reverse_code=uninstall),
    ]
