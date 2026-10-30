"""Protect payroll compensation-plan identity and earning periods.

Additive triggers only. Existing payroll integrity and payment issuance
triggers remain installed. Do not alter approved historical records.
"""

from django.db import migrations


SQLITE_INVALID_PLAN = """
    NOT EXISTS (
        SELECT 1
        FROM core_employeecompensationplan AS plan
        WHERE plan.id = NEW.compensation_plan_id
          AND plan.employee_id = NEW.employee_id
          AND plan.status = 'APPROVED'
          AND plan.effective_date <= NEW.payroll_period_start
    )
    OR NEW.payroll_period_start > NEW.payroll_period_end
    OR EXISTS (
        SELECT 1
        FROM core_employeecompensationplan AS plan
        JOIN core_employeecompensationplan AS other
          ON other.employee_id = plan.employee_id
        WHERE plan.id = NEW.compensation_plan_id
          AND other.status = 'APPROVED'
          AND other.id != plan.id
          AND other.effective_date > plan.effective_date
          AND other.effective_date <= NEW.payroll_period_end
    )
    OR EXISTS (
        SELECT 1
        FROM core_employeecompensationplan AS a
        JOIN core_employeecompensationplan AS b
          ON b.employee_id = a.employee_id
         AND b.effective_date = a.effective_date
         AND b.id != a.id
        WHERE a.employee_id = NEW.employee_id
          AND a.status = 'APPROVED'
          AND b.status = 'APPROVED'
    )
"""


POSTGRESQL_INVALID_PLAN = """
    NOT EXISTS (
        SELECT 1
        FROM core_employeecompensationplan AS plan
        WHERE plan.id = NEW.compensation_plan_id
          AND plan.employee_id = NEW.employee_id
          AND plan.status = 'APPROVED'
          AND plan.effective_date <= NEW.payroll_period_start
    )
    OR NEW.payroll_period_start > NEW.payroll_period_end
    OR EXISTS (
        SELECT 1
        FROM core_employeecompensationplan AS plan
        JOIN core_employeecompensationplan AS other
          ON other.employee_id = plan.employee_id
        WHERE plan.id = NEW.compensation_plan_id
          AND other.status = 'APPROVED'
          AND other.id <> plan.id
          AND other.effective_date > plan.effective_date
          AND other.effective_date <= NEW.payroll_period_end
    )
    OR EXISTS (
        SELECT 1
        FROM core_employeecompensationplan AS a
        JOIN core_employeecompensationplan AS b
          ON b.employee_id = a.employee_id
         AND b.effective_date = a.effective_date
         AND b.id <> a.id
        WHERE a.employee_id = NEW.employee_id
          AND a.status = 'APPROVED'
          AND b.status = 'APPROVED'
    )
"""


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for action, condition in (
            ("insert", ""),
            ("update", "WHEN OLD.status = 'DRAFT'"),
        ):
            name = "gecc_payroll_plan_relationship_" + action
            event = "INSERT" if action == "insert" else "UPDATE"
            schema_editor.execute(
                f"""
                CREATE TRIGGER {name}
                BEFORE {event} ON core_employeepayrollrecord
                {condition}
                BEGIN
                    SELECT CASE WHEN
                        ({SQLITE_INVALID_PLAN})
                    THEN RAISE(
                        ABORT,
                        'Payroll compensation plan does not match earning period'
                    ) END;
                END
                """
            )

    elif vendor == "postgresql":
        schema_editor.execute(
            f"""
            CREATE FUNCTION gecc_payroll_plan_relationship_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'INSERT'
                   OR (TG_OP = 'UPDATE' AND OLD.status = 'DRAFT')
                THEN
                    IF ({POSTGRESQL_INVALID_PLAN}) THEN
                        RAISE EXCEPTION
                            'Payroll compensation plan does not match earning period';
                    END IF;
                END IF;
                RETURN NEW;
            END $$;
            """
        )
        schema_editor.execute(
            """
            CREATE TRIGGER gecc_payroll_plan_relationship_guard
            BEFORE INSERT OR UPDATE
            ON core_employeepayrollrecord
            FOR EACH ROW
            EXECUTE FUNCTION gecc_payroll_plan_relationship_guard();
            """
        )
    else:
        raise RuntimeError(
            "SAFETY STOP: Unsupported payroll database vendor."
        )


def uninstall(apps, schema_editor):
    # This security migration must not silently remove financial guards.
    raise RuntimeError(
        "SAFETY STOP: Payroll relationship guards require "
        "a separately reviewed rollback migration."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0067_user_session_security"),
    ]

    operations = [
        migrations.RunPython(install, reverse_code=uninstall),
    ]
