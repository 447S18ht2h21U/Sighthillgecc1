from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":

        schema_editor.execute("""
            CREATE TRIGGER gecc_payroll_summary_insert_guard
            BEFORE INSERT ON core_payrollsummary
            BEGIN
                SELECT CASE WHEN
                    NEW.status != 'DRAFT'
                    OR NEW.approved_by_id IS NOT NULL
                    OR NEW.approved_at IS NOT NULL
                THEN RAISE(
                    ABORT,
                    'New payroll summaries must be draft'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_payroll_summary_update_guard
            BEFORE UPDATE ON core_payrollsummary
            BEGIN
                SELECT CASE WHEN OLD.status = 'APPROVED'
                THEN RAISE(
                    ABORT,
                    'Approved payroll summaries are immutable'
                )
                END;

                SELECT CASE WHEN
                    NEW.status = 'APPROVED'
                    AND (
                        OLD.status != 'DRAFT'
                        OR NEW.approved_by_id IS NULL
                        OR NEW.approved_at IS NULL
                        OR NEW.period_start != OLD.period_start
                        OR NEW.period_end != OLD.period_end
                        OR NEW.contractor_total != OLD.contractor_total
                        OR NEW.employee_total != OLD.employee_total
                        OR NEW.total_payroll_expense != OLD.total_payroll_expense
                        OR NEW.summary_snapshot != OLD.summary_snapshot
                    )
                THEN RAISE(
                    ABORT,
                    'Invalid payroll summary approval'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_payroll_summary_delete_guard
            BEFORE DELETE ON core_payrollsummary
            WHEN OLD.status = 'APPROVED'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Approved payroll summaries cannot be deleted'
                );
            END
        """)

    elif vendor == "postgresql":

        schema_editor.execute("""
            CREATE FUNCTION gecc_payroll_summary_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION
                        'Approved payroll summaries cannot be deleted';
                    END IF;
                    RETURN OLD;
                END IF;

                IF TG_OP = 'INSERT' THEN
                    IF NEW.status <> 'DRAFT'
                       OR NEW.approved_by_id IS NOT NULL
                       OR NEW.approved_at IS NOT NULL THEN
                        RAISE EXCEPTION
                        'New payroll summaries must be draft';
                    END IF;
                ELSE
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION
                        'Approved payroll summaries are immutable';
                    END IF;
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_payroll_summary_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON core_payrollsummary
            FOR EACH ROW
            EXECUTE FUNCTION gecc_payroll_summary_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for name in [
            "gecc_payroll_summary_insert_guard",
            "gecc_payroll_summary_update_guard",
            "gecc_payroll_summary_delete_guard",
        ]:
            schema_editor.execute(
                f"DROP TRIGGER IF EXISTS {name}"
            )

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_payroll_summary_guard
            ON core_payrollsummary;

            DROP FUNCTION IF EXISTS gecc_payroll_summary_guard();
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0029_payrollsummary"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]