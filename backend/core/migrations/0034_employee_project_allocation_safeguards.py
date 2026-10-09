from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":

        schema_editor.execute("""
            CREATE TRIGGER gecc_employee_project_allocation_insert_guard
            BEFORE INSERT ON core_employeeprojectallocation
            BEGIN
                SELECT CASE WHEN
                    NEW.status != 'DRAFT'
                    OR NEW.approved_by_id IS NOT NULL
                    OR NEW.approved_at IS NOT NULL
                THEN RAISE(
                    ABORT,
                    'New employee project allocations must be draft'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_employee_project_allocation_update_guard
            BEFORE UPDATE ON core_employeeprojectallocation
            BEGIN
                SELECT CASE WHEN OLD.status = 'APPROVED'
                THEN RAISE(
                    ABORT,
                    'Approved employee project allocations are immutable'
                )
                END;

                SELECT CASE WHEN
                    NEW.status = 'APPROVED'
                    AND (
                        NEW.approved_by_id IS NULL
                        OR NEW.approved_at IS NULL
                        OR NEW.employee_id != OLD.employee_id
                        OR NEW.project_id != OLD.project_id
                        OR NEW.allocation_percentage != OLD.allocation_percentage
                        OR NEW.effective_date != OLD.effective_date
                    )
                THEN RAISE(
                    ABORT,
                    'Invalid employee project allocation approval'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_employee_project_allocation_delete_guard
            BEFORE DELETE ON core_employeeprojectallocation
            WHEN OLD.status = 'APPROVED'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Approved employee project allocations cannot be deleted'
                );
            END
        """)

    elif vendor == "postgresql":

        schema_editor.execute("""
            CREATE FUNCTION gecc_employee_project_allocation_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN

                IF TG_OP = 'DELETE' THEN
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION
                        'Approved employee project allocations cannot be deleted';
                    END IF;
                    RETURN OLD;
                END IF;

                IF TG_OP = 'INSERT' THEN
                    IF NEW.status <> 'DRAFT'
                    OR NEW.approved_by_id IS NOT NULL
                    OR NEW.approved_at IS NOT NULL THEN
                        RAISE EXCEPTION
                        'New employee project allocations must be draft';
                    END IF;

                ELSE
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION
                        'Approved employee project allocations are immutable';
                    END IF;
                END IF;

                RETURN NEW;

            END $$;

            CREATE TRIGGER gecc_employee_project_allocation_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON core_employeeprojectallocation
            FOR EACH ROW
            EXECUTE FUNCTION gecc_employee_project_allocation_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for name in [
            "gecc_employee_project_allocation_insert_guard",
            "gecc_employee_project_allocation_update_guard",
            "gecc_employee_project_allocation_delete_guard",
        ]:
            schema_editor.execute(
                f"DROP TRIGGER IF EXISTS {name}"
            )

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_employee_project_allocation_guard
            ON core_employeeprojectallocation;

            DROP FUNCTION IF EXISTS gecc_employee_project_allocation_guard();
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0033_employeeprojectallocation"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]