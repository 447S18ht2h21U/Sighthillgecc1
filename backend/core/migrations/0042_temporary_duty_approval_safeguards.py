from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    eligible_roles = """
        (
            (permanent_role IN ('CEO', 'COMPTROLLER')
             AND temporary_role IN ('SALES_MANAGER', 'INSTALLATION_MANAGER'))
            OR
            (permanent_role IN ('SALES_MANAGER', 'INSTALLATION_MANAGER')
             AND temporary_role IN ('SALES_ASSOCIATE', 'TECHNICIAN'))
        )
    """

    if vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER gecc_temporary_duty_approval_guard
            BEFORE UPDATE ON core_temporarydutyauthorization
            WHEN OLD.status = 'REQUESTED' AND NEW.status = 'APPROVED'
            BEGIN
                SELECT CASE WHEN
                    NEW.approved_by_id IS NULL
                    OR NEW.approved_by_id = NEW.employee_id
                    OR NEW.decided_at IS NULL
                    OR NOT EXISTS (
                        SELECT 1 FROM core_user employee
                        JOIN core_user approver
                          ON approver.id = NEW.approved_by_id
                        WHERE employee.id = NEW.employee_id
                          AND employee.is_active = 1
                          AND approver.is_active = 1
                          AND employee.role = NEW.permanent_role
                          AND (
                            (employee.role = 'CEO'
                             AND approver.role = 'COMPTROLLER')
                            OR
                            (employee.role = 'COMPTROLLER'
                             AND approver.role = 'CEO')
                            OR
                            (employee.role IN ('SALES_MANAGER', 'INSTALLATION_MANAGER')
                             AND approver.role IN ('CEO', 'COMPTROLLER'))
                          )
                          AND (
                            (employee.role IN ('CEO', 'COMPTROLLER')
                             AND NEW.temporary_role IN ('SALES_MANAGER', 'INSTALLATION_MANAGER'))
                            OR
                            (employee.role IN ('SALES_MANAGER', 'INSTALLATION_MANAGER')
                             AND NEW.temporary_role IN ('SALES_ASSOCIATE', 'TECHNICIAN'))
                          )
                    )
                THEN RAISE(ABORT, 'Temporary-duty approver or role is not authorized')
                END;
            END;
        """)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_temporary_duty_approval_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.status = 'REQUESTED' AND NEW.status = 'APPROVED' THEN
                    IF NEW.approved_by_id IS NULL
                        OR NEW.approved_by_id = NEW.employee_id
                        OR NEW.decided_at IS NULL
                        OR NOT EXISTS (
                            SELECT 1 FROM core_user employee
                            JOIN core_user approver
                              ON approver.id = NEW.approved_by_id
                            WHERE employee.id = NEW.employee_id
                              AND employee.is_active = TRUE
                              AND approver.is_active = TRUE
                              AND employee.role = NEW.permanent_role
                              AND (
                                (employee.role = 'CEO'
                                 AND approver.role = 'COMPTROLLER')
                                OR
                                (employee.role = 'COMPTROLLER'
                                 AND approver.role = 'CEO')
                                OR
                                (employee.role IN ('SALES_MANAGER', 'INSTALLATION_MANAGER')
                                 AND approver.role IN ('CEO', 'COMPTROLLER'))
                              )
                              AND (
                                (employee.role IN ('CEO', 'COMPTROLLER')
                                 AND NEW.temporary_role IN ('SALES_MANAGER', 'INSTALLATION_MANAGER'))
                                OR
                                (employee.role IN ('SALES_MANAGER', 'INSTALLATION_MANAGER')
                                 AND NEW.temporary_role IN ('SALES_ASSOCIATE', 'TECHNICIAN'))
                              )
                        )
                    THEN
                        RAISE EXCEPTION 'Temporary-duty approver or role is not authorized';
                    END IF;
                END IF;
                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_temporary_duty_approval_guard
            BEFORE UPDATE ON core_temporarydutyauthorization
            FOR EACH ROW
            EXECUTE FUNCTION gecc_temporary_duty_approval_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS gecc_temporary_duty_approval_guard;"
        )
    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_temporary_duty_approval_guard
            ON core_temporarydutyauthorization;
            DROP FUNCTION IF EXISTS gecc_temporary_duty_approval_guard();
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0041_temporary_duty_insert_safeguards"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]
