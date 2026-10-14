from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    immutable_sqlite = '''
        NEW.temporary_duty_id IS NOT OLD.temporary_duty_id
        OR NEW.employee_id IS NOT OLD.employee_id
        OR NEW.project_id IS NOT OLD.project_id
        OR NEW.requested_by_id IS NOT OLD.requested_by_id
        OR NEW.reason IS NOT OLD.reason
        OR NEW.starts_at IS NOT OLD.starts_at
        OR NEW.ends_at IS NOT OLD.ends_at
        OR NEW.created_at IS NOT OLD.created_at
    '''

    immutable_postgres = '''
        NEW.temporary_duty_id IS DISTINCT FROM OLD.temporary_duty_id
        OR NEW.employee_id IS DISTINCT FROM OLD.employee_id
        OR NEW.project_id IS DISTINCT FROM OLD.project_id
        OR NEW.requested_by_id IS DISTINCT FROM OLD.requested_by_id
        OR NEW.reason IS DISTINCT FROM OLD.reason
        OR NEW.starts_at IS DISTINCT FROM OLD.starts_at
        OR NEW.ends_at IS DISTINCT FROM OLD.ends_at
        OR NEW.created_at IS DISTINCT FROM OLD.created_at
    '''

    transitions = '''
        (OLD.status = 'REQUESTED'
         AND NEW.status IN ('REQUESTED', 'APPROVED', 'REJECTED'))
        OR
        (OLD.status = 'APPROVED'
         AND NEW.status IN ('APPROVED', 'REVOKED', 'COMPLETED'))
        OR
        (OLD.status IN ('REJECTED', 'REVOKED', 'COMPLETED')
         AND NEW.status = OLD.status)
    '''

    if vendor == "sqlite":
        schema_editor.execute(f'''
            CREATE TRIGGER gecc_temporary_project_access_update_guard
            BEFORE UPDATE ON core_temporaryprojectaccessauthorization
            BEGIN
                SELECT CASE WHEN {immutable_sqlite}
                THEN RAISE(ABORT, 'Project-access request details are immutable')
                END;

                SELECT CASE WHEN NOT ({transitions})
                THEN RAISE(ABORT, 'Invalid project-access status transition')
                END;

                SELECT CASE WHEN
                    NEW.status = 'APPROVED'
                    AND (
                        NEW.approved_by_id IS NULL
                        OR NEW.approved_by_id = NEW.employee_id
                        OR NEW.approved_by_id = NEW.requested_by_id
                        OR NEW.decided_at IS NULL
                    )
                THEN RAISE(ABORT, 'Independent project-access approval required')
                END;

                SELECT CASE WHEN
                    OLD.status != 'REQUESTED'
                    AND (
                        NEW.approved_by_id IS NOT OLD.approved_by_id
                        OR NEW.decided_at IS NOT OLD.decided_at
                    )
                THEN RAISE(ABORT, 'Project-access approval evidence is immutable')
                END;

                SELECT CASE WHEN
                    NEW.status = 'REVOKED' AND NEW.revoked_at IS NULL
                THEN RAISE(ABORT, 'Project-access revocation timestamp required')
                END;

                SELECT CASE WHEN
                    NEW.status = 'COMPLETED' AND NEW.closed_at IS NULL
                THEN RAISE(ABORT, 'Project-access completion timestamp required')
                END;

                SELECT CASE WHEN
                    NEW.status = 'REJECTED' AND NEW.decided_at IS NULL
                THEN RAISE(ABORT, 'Project-access rejection timestamp required')
                END;

                SELECT CASE WHEN
                    OLD.status = 'REVOKED'
                    AND NEW.revoked_at IS NOT OLD.revoked_at
                THEN RAISE(ABORT, 'Project-access revocation evidence is immutable')
                END;

                SELECT CASE WHEN
                    OLD.status = 'COMPLETED'
                    AND NEW.closed_at IS NOT OLD.closed_at
                THEN RAISE(ABORT, 'Project-access completion evidence is immutable')
                END;
            END;
        ''')

        schema_editor.execute('''
            CREATE TRIGGER gecc_temporary_project_access_delete_guard
            BEFORE DELETE ON core_temporaryprojectaccessauthorization
            BEGIN
                SELECT RAISE(ABORT, 'Project-access authorizations cannot be deleted');
            END;
        ''')

    elif vendor == "postgresql":
        schema_editor.execute(f'''
            CREATE FUNCTION gecc_temporary_project_access_update_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF {immutable_postgres}
                THEN
                    RAISE EXCEPTION 'Project-access request details are immutable';
                END IF;

                IF NOT ({transitions})
                THEN
                    RAISE EXCEPTION 'Invalid project-access status transition';
                END IF;

                IF NEW.status = 'APPROVED'
                    AND (
                        NEW.approved_by_id IS NULL
                        OR NEW.approved_by_id = NEW.employee_id
                        OR NEW.approved_by_id = NEW.requested_by_id
                        OR NEW.decided_at IS NULL
                    )
                THEN
                    RAISE EXCEPTION 'Independent project-access approval required';
                END IF;

                IF OLD.status != 'REQUESTED'
                    AND (
                        NEW.approved_by_id IS DISTINCT FROM OLD.approved_by_id
                        OR NEW.decided_at IS DISTINCT FROM OLD.decided_at
                    )
                THEN
                    RAISE EXCEPTION 'Project-access approval evidence is immutable';
                END IF;

                IF NEW.status = 'REVOKED' AND NEW.revoked_at IS NULL
                THEN
                    RAISE EXCEPTION 'Project-access revocation timestamp required';
                END IF;

                IF NEW.status = 'COMPLETED' AND NEW.closed_at IS NULL
                THEN
                    RAISE EXCEPTION 'Project-access completion timestamp required';
                END IF;

                IF NEW.status = 'REJECTED' AND NEW.decided_at IS NULL
                THEN
                    RAISE EXCEPTION 'Project-access rejection timestamp required';
                END IF;

                IF OLD.status = 'REVOKED'
                    AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at
                THEN
                    RAISE EXCEPTION 'Project-access revocation evidence is immutable';
                END IF;

                IF OLD.status = 'COMPLETED'
                    AND NEW.closed_at IS DISTINCT FROM OLD.closed_at
                THEN
                    RAISE EXCEPTION 'Project-access completion evidence is immutable';
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_temporary_project_access_update_guard
            BEFORE UPDATE ON core_temporaryprojectaccessauthorization
            FOR EACH ROW
            EXECUTE FUNCTION gecc_temporary_project_access_update_guard();

            CREATE FUNCTION gecc_temporary_project_access_delete_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'Project-access authorizations cannot be deleted';
            END $$;

            CREATE TRIGGER gecc_temporary_project_access_delete_guard
            BEFORE DELETE ON core_temporaryprojectaccessauthorization
            FOR EACH ROW
            EXECUTE FUNCTION gecc_temporary_project_access_delete_guard();
        ''')


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS gecc_temporary_project_access_update_guard;"
        )
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS gecc_temporary_project_access_delete_guard;"
        )

    elif vendor == "postgresql":
        schema_editor.execute('''
            DROP TRIGGER IF EXISTS gecc_temporary_project_access_update_guard
            ON core_temporaryprojectaccessauthorization;
            DROP TRIGGER IF EXISTS gecc_temporary_project_access_delete_guard
            ON core_temporaryprojectaccessauthorization;
            DROP FUNCTION IF EXISTS gecc_temporary_project_access_update_guard();
            DROP FUNCTION IF EXISTS gecc_temporary_project_access_delete_guard();
        ''')


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0049_temporary_project_access_insert_safeguards"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]
