from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER gecc_temporary_duty_lifecycle_guard
            BEFORE UPDATE ON core_temporarydutyauthorization
            BEGIN
                SELECT CASE WHEN
                    NEW.status = 'REJECTED'
                    AND NEW.decided_at IS NULL
                THEN RAISE(ABORT, 'Rejection requires a decision timestamp')
                END;

                SELECT CASE WHEN
                    NEW.status = 'REVOKED'
                    AND NEW.revoked_at IS NULL
                THEN RAISE(ABORT, 'Revocation requires a timestamp')
                END;

                SELECT CASE WHEN
                    NEW.status = 'COMPLETED'
                    AND NEW.closed_at IS NULL
                THEN RAISE(ABORT, 'Completion requires a timestamp')
                END;

                SELECT CASE WHEN
                    OLD.status = 'REVOKED'
                    AND NEW.revoked_at IS NOT OLD.revoked_at
                THEN RAISE(ABORT, 'Revocation evidence is immutable')
                END;

                SELECT CASE WHEN
                    OLD.status = 'COMPLETED'
                    AND NEW.closed_at IS NOT OLD.closed_at
                THEN RAISE(ABORT, 'Completion evidence is immutable')
                END;

                SELECT CASE WHEN
                    OLD.status = 'REJECTED'
                    AND NEW.decided_at IS NOT OLD.decided_at
                THEN RAISE(ABORT, 'Rejection evidence is immutable')
                END;
            END;
        """)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_temporary_duty_lifecycle_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.status = 'REJECTED'
                    AND NEW.decided_at IS NULL
                THEN
                    RAISE EXCEPTION 'Rejection requires a decision timestamp';
                END IF;

                IF NEW.status = 'REVOKED'
                    AND NEW.revoked_at IS NULL
                THEN
                    RAISE EXCEPTION 'Revocation requires a timestamp';
                END IF;

                IF NEW.status = 'COMPLETED'
                    AND NEW.closed_at IS NULL
                THEN
                    RAISE EXCEPTION 'Completion requires a timestamp';
                END IF;

                IF OLD.status = 'REVOKED'
                    AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at
                THEN
                    RAISE EXCEPTION 'Revocation evidence is immutable';
                END IF;

                IF OLD.status = 'COMPLETED'
                    AND NEW.closed_at IS DISTINCT FROM OLD.closed_at
                THEN
                    RAISE EXCEPTION 'Completion evidence is immutable';
                END IF;

                IF OLD.status = 'REJECTED'
                    AND NEW.decided_at IS DISTINCT FROM OLD.decided_at
                THEN
                    RAISE EXCEPTION 'Rejection evidence is immutable';
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_temporary_duty_lifecycle_guard
            BEFORE UPDATE ON core_temporarydutyauthorization
            FOR EACH ROW
            EXECUTE FUNCTION gecc_temporary_duty_lifecycle_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS gecc_temporary_duty_lifecycle_guard;"
        )
    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_temporary_duty_lifecycle_guard
            ON core_temporarydutyauthorization;
            DROP FUNCTION IF EXISTS gecc_temporary_duty_lifecycle_guard();
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0042_temporary_duty_approval_safeguards"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]
