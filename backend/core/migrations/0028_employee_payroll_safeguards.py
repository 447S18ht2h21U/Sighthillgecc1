from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":

        schema_editor.execute("""
            CREATE TRIGGER gecc_employee_comp_plan_update_guard
            BEFORE UPDATE ON core_employeecompensationplan
            BEGIN
                SELECT CASE WHEN OLD.status = 'APPROVED'
                THEN RAISE(
                    ABORT,
                    'Approved employee compensation plans are immutable'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_employee_payroll_insert_guard
            BEFORE INSERT ON core_employeepayrollrecord
            BEGIN
                SELECT CASE WHEN
                    NEW.status != 'DRAFT'
                    OR NEW.approved_by_id IS NOT NULL
                    OR NEW.approved_at IS NOT NULL
                    OR NEW.paid_at IS NOT NULL
                THEN RAISE(
                    ABORT,
                    'New employee payroll records must be draft'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_employee_payroll_update_guard
            BEFORE UPDATE ON core_employeepayrollrecord
            BEGIN
                SELECT CASE WHEN OLD.status = 'PAID'
                THEN RAISE(
                    ABORT,
                    'Paid employee payroll records are immutable'
                )
                END;

                SELECT CASE WHEN OLD.status = 'APPROVED'
                    AND (
                        NEW.employee_id != OLD.employee_id
                        OR NEW.compensation_plan_id != OLD.compensation_plan_id
                        OR NEW.kind != OLD.kind
                        OR NEW.payroll_period_start != OLD.payroll_period_start
                        OR NEW.payroll_period_end != OLD.payroll_period_end
                        OR NEW.gross_amount != OLD.gross_amount
                        OR NEW.deduction_amount != OLD.deduction_amount
                        OR NEW.net_amount != OLD.net_amount
                        OR NEW.calculation_snapshot != OLD.calculation_snapshot
                    )
                THEN RAISE(
                    ABORT,
                    'Approved employee payroll cannot change'
                )
                END;

                SELECT CASE WHEN
                    NEW.status = 'APPROVED'
                    AND (
                        OLD.status != 'DRAFT'
                        OR NEW.approved_by_id IS NULL
                        OR NEW.approved_at IS NULL
                    )
                THEN RAISE(
                    ABORT,
                    'Invalid employee payroll approval'
                )
                END;

                SELECT CASE WHEN
                    NEW.status = 'PAID'
                    AND (
                        OLD.status != 'APPROVED'
                        OR NEW.paid_at IS NULL
                    )
                THEN RAISE(
                    ABORT,
                    'Invalid employee payroll settlement'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_employee_payroll_delete_guard
            BEFORE DELETE ON core_employeepayrollrecord
            WHEN OLD.status IN ('APPROVED','PAID')
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Approved or paid employee payroll cannot be deleted'
                );
            END
        """)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_employee_payroll_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status IN ('APPROVED','PAID') THEN
                        RAISE EXCEPTION
                        'Approved or paid employee payroll cannot be deleted';
                    END IF;
                    RETURN OLD;
                END IF;

                IF TG_OP = 'INSERT' THEN
                    IF NEW.status <> 'DRAFT'
                       OR NEW.approved_by_id IS NOT NULL
                       OR NEW.approved_at IS NOT NULL
                       OR NEW.paid_at IS NOT NULL THEN
                        RAISE EXCEPTION
                        'New employee payroll records must be draft';
                    END IF;
                ELSE
                    IF OLD.status = 'PAID' THEN
                        RAISE EXCEPTION
                        'Paid employee payroll records are immutable';
                    END IF;
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_employee_payroll_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON core_employeepayrollrecord
            FOR EACH ROW
            EXECUTE FUNCTION gecc_employee_payroll_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for name in [
            "gecc_employee_comp_plan_update_guard",
            "gecc_employee_payroll_insert_guard",
            "gecc_employee_payroll_update_guard",
            "gecc_employee_payroll_delete_guard",
        ]:
            schema_editor.execute(
                f"DROP TRIGGER IF EXISTS {name}"
            )

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_employee_payroll_guard
            ON core_employeepayrollrecord;

            DROP FUNCTION IF EXISTS gecc_employee_payroll_guard();
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0027_employee_employeecompensationplan_and_more"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]