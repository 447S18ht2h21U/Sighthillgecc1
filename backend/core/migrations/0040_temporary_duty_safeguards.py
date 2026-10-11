from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER gecc_temporary_duty_update_guard
            BEFORE UPDATE ON core_temporarydutyauthorization
            BEGIN
                SELECT CASE WHEN
                    NEW.employee_id != OLD.employee_id
                    OR NEW.permanent_role != OLD.permanent_role
                    OR NEW.temporary_role != OLD.temporary_role
                    OR NEW.requested_by_id != OLD.requested_by_id
                    OR NEW.reason != OLD.reason
                    OR NEW.starts_at != OLD.starts_at
                    OR NEW.ends_at != OLD.ends_at
                    OR NEW.created_at != OLD.created_at
                THEN RAISE(ABORT, 'Temporary-duty request details are immutable')
                END;

                SELECT CASE WHEN NOT (
                    (OLD.status = 'REQUESTED' AND NEW.status IN ('REQUESTED', 'APPROVED', 'REJECTED'))
                    OR (OLD.status = 'APPROVED' AND NEW.status IN ('APPROVED', 'REVOKED', 'COMPLETED'))
                    OR (OLD.status IN ('REJECTED', 'REVOKED', 'COMPLETED') AND NEW.status = OLD.status)
                ) THEN RAISE(ABORT, 'Invalid temporary-duty status transition')
                END;

                SELECT CASE WHEN
                    NEW.status = 'APPROVED'
                    AND (NEW.approved_by_id IS NULL OR NEW.approved_by_id = NEW.employee_id OR NEW.decided_at IS NULL)
                THEN RAISE(ABORT, 'Temporary-duty approval requires independent authorization')
                END;

                SELECT CASE WHEN
                    OLD.status != 'REQUESTED'
                    AND (
                        NEW.approved_by_id IS NOT OLD.approved_by_id
                        OR NEW.decided_at IS NOT OLD.decided_at
                    )
                THEN RAISE(ABORT, 'Temporary-duty approval evidence is immutable')
                END;
            END;
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_temporary_duty_delete_guard
            BEFORE DELETE ON core_temporarydutyauthorization
            BEGIN
                SELECT RAISE(ABORT, 'Temporary-duty authorizations cannot be deleted');
            END;
        """)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_temporary_duty_update_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.employee_id IS DISTINCT FROM OLD.employee_id
                    OR NEW.permanent_role IS DISTINCT FROM OLD.permanent_role
                    OR NEW.temporary_role IS DISTINCT FROM OLD.temporary_role
                    OR NEW.requested_by_id IS DISTINCT FROM OLD.requested_by_id
                    OR NEW.reason IS DISTINCT FROM OLD.reason
                    OR NEW.starts_at IS DISTINCT FROM OLD.starts_at
                    OR NEW.ends_at IS DISTINCT FROM OLD.ends_at
                    OR NEW.created_at IS DISTINCT FROM OLD.created_at
                THEN
                    RAISE EXCEPTION 'Temporary-duty request details are immutable';
                END IF;

                IF NOT (
                    (OLD.status = 'REQUESTED' AND NEW.status IN ('REQUESTED', 'APPROVED', 'REJECTED'))
                    OR (OLD.status = 'APPROVED' AND NEW.status IN ('APPROVED', 'REVOKED', 'COMPLETED'))
                    OR (OLD.status IN ('REJECTED', 'REVOKED', 'COMPLETED') AND NEW.status = OLD.status)
                ) THEN
                    RAISE EXCEPTION 'Invalid temporary-duty status transition';
                END IF;

                IF NEW.status = 'APPROVED'
                    AND (NEW.approved_by_id IS NULL OR NEW.approved_by_id = NEW.employee_id OR NEW.decided_at IS NULL)
                THEN
                    RAISE EXCEPTION 'Temporary-duty approval requires independent authorization';
                END IF;

                IF OLD.status != 'REQUESTED'
                    AND (
                        NEW.approved_by_id IS DISTINCT FROM OLD.approved_by_id
                        OR NEW.decided_at IS DISTINCT FROM OLD.decided_at
                    )
                THEN
                    RAISE EXCEPTION 'Temporary-duty approval evidence is immutable';
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_temporary_duty_update_guard
            BEFORE UPDATE ON core_temporarydutyauthorization
            FOR EACH ROW
            EXECUTE FUNCTION gecc_temporary_duty_update_guard();

            CREATE FUNCTION gecc_temporary_duty_delete_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'Temporary-duty authorizations cannot be deleted';
            END $$;

            CREATE TRIGGER gecc_temporary_duty_delete_guard
            BEFORE DELETE ON core_temporarydutyauthorization
            FOR EACH ROW
            EXECUTE FUNCTION gecc_temporary_duty_delete_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER IF EXISTS gecc_temporary_duty_update_guard;")
        schema_editor.execute("DROP TRIGGER IF EXISTS gecc_temporary_duty_delete_guard;")

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_temporary_duty_update_guard
            ON core_temporarydutyauthorization;
            DROP TRIGGER IF EXISTS gecc_temporary_duty_delete_guard
            ON core_temporarydutyauthorization;
            DROP FUNCTION IF EXISTS gecc_temporary_duty_update_guard();
            DROP FUNCTION IF EXISTS gecc_temporary_duty_delete_guard();
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0039_temporary_duty_foundation"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]
