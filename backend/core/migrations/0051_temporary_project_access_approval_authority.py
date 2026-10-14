from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    role_rule = '''
        (
            (employee.role = 'CEO' AND approver.role = 'COMPTROLLER')
            OR
            (employee.role = 'COMPTROLLER' AND approver.role = 'CEO')
            OR
            (employee.role IN ('SALES_MANAGER', 'INSTALLATION_MANAGER')
             AND approver.role IN ('CEO', 'COMPTROLLER'))
        )
    '''

    duty_role_rule = '''
        (
            (employee.role IN ('CEO', 'COMPTROLLER')
             AND duty.temporary_role IN ('SALES_MANAGER', 'INSTALLATION_MANAGER'))
            OR
            (employee.role IN ('SALES_MANAGER', 'INSTALLATION_MANAGER')
             AND duty.temporary_role IN ('SALES_ASSOCIATE', 'TECHNICIAN'))
        )
    '''

    if vendor == "sqlite":
        now_expression = "STRFTIME('%Y-%m-%d %H:%M:%f', 'now')"
        active = "1"
        inequality = "!="
        function_start = ""
        function_end = ""

    elif vendor == "postgresql":
        now_expression = "CURRENT_TIMESTAMP"
        active = "TRUE"
        inequality = "<>"
        function_start = ""
        function_end = ""

    else:
        raise RuntimeError(
            f"Unsupported database for project-access approval safeguards: {vendor}"
        )

    validation = f'''
        EXISTS (
            SELECT 1
            FROM core_user employee
            JOIN core_user approver
              ON approver.id = NEW.approved_by_id
            JOIN core_temporarydutyauthorization duty
              ON duty.id = NEW.temporary_duty_id
            JOIN core_user duty_approver
              ON duty_approver.id = duty.approved_by_id
            WHERE employee.id = NEW.employee_id
              AND employee.is_active = {active}
              AND approver.is_active = {active}
              AND duty_approver.is_active = {active}
              AND approver.id {inequality} employee.id
              AND approver.id {inequality} NEW.requested_by_id
              AND {role_rule}
              AND duty.employee_id = employee.id
              AND duty.permanent_role = employee.role
              AND {duty_role_rule}
              AND duty.status = 'APPROVED'
              AND duty.approved_by_id {inequality} employee.id
              AND duty.decided_at IS NOT NULL
              AND duty.revoked_at IS NULL
              AND duty.closed_at IS NULL
              AND (
                  (employee.role = 'CEO'
                   AND duty_approver.role = 'COMPTROLLER')
                  OR
                  (employee.role = 'COMPTROLLER'
                   AND duty_approver.role = 'CEO')
                  OR
                  (employee.role IN ('SALES_MANAGER', 'INSTALLATION_MANAGER')
                   AND duty_approver.role IN ('CEO', 'COMPTROLLER'))
              )
              AND duty.starts_at <= {now_expression}
              AND duty.ends_at > {now_expression}
              AND duty.decided_at <= {now_expression}
              AND NEW.starts_at >= duty.starts_at
              AND NEW.ends_at <= duty.ends_at
              AND NEW.ends_at > {now_expression}
              AND NEW.ends_at > NEW.starts_at
        )
    '''

    if vendor == "sqlite":
        schema_editor.execute(f'''
            CREATE TRIGGER gecc_temporary_project_access_approval_authority
            BEFORE UPDATE ON core_temporaryprojectaccessauthorization
            WHEN OLD.status = 'REQUESTED' AND NEW.status = 'APPROVED'
            BEGIN
                SELECT CASE WHEN NOT ({validation})
                THEN RAISE(
                    ABORT,
                    'Project-access approver or temporary duty is not authorized'
                )
                END;
            END;
        ''')

    elif vendor == "postgresql":
        schema_editor.execute(f'''
            CREATE FUNCTION gecc_temporary_project_access_approval_authority()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.status = 'REQUESTED' AND NEW.status = 'APPROVED' THEN
                    IF NOT ({validation}) THEN
                        RAISE EXCEPTION
                            'Project-access approver or temporary duty is not authorized';
                    END IF;
                END IF;
                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_temporary_project_access_approval_authority
            BEFORE UPDATE ON core_temporaryprojectaccessauthorization
            FOR EACH ROW
            EXECUTE FUNCTION gecc_temporary_project_access_approval_authority();
        ''')


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS "
            "gecc_temporary_project_access_approval_authority;"
        )

    elif vendor == "postgresql":
        schema_editor.execute('''
            DROP TRIGGER IF EXISTS
                gecc_temporary_project_access_approval_authority
            ON core_temporaryprojectaccessauthorization;

            DROP FUNCTION IF EXISTS
                gecc_temporary_project_access_approval_authority();
        ''')


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0050_temporary_project_access_update_safeguards"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]
