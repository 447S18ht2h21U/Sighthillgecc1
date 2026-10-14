from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER gecc_temporary_project_access_insert_guard
            BEFORE INSERT ON core_temporaryprojectaccessauthorization
            BEGIN
                SELECT CASE WHEN
                    NEW.status IS NULL
                    OR NEW.status != 'REQUESTED'
                    OR NEW.approved_by_id IS NOT NULL
                    OR NEW.decided_at IS NOT NULL
                    OR NEW.revoked_at IS NOT NULL
                    OR NEW.closed_at IS NOT NULL
                THEN RAISE(ABORT, 'Temporary project access must begin as an unapproved request')
                END;
            END;
        """)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_temporary_project_access_insert_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.status IS NULL
                    OR NEW.status != 'REQUESTED'
                    OR NEW.approved_by_id IS NOT NULL
                    OR NEW.decided_at IS NOT NULL
                    OR NEW.revoked_at IS NOT NULL
                    OR NEW.closed_at IS NOT NULL
                THEN
                    RAISE EXCEPTION 'Temporary project access must begin as an unapproved request';
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_temporary_project_access_insert_guard
            BEFORE INSERT ON core_temporaryprojectaccessauthorization
            FOR EACH ROW
            EXECUTE FUNCTION gecc_temporary_project_access_insert_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS gecc_temporary_project_access_insert_guard;"
        )

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_temporary_project_access_insert_guard
            ON core_temporaryprojectaccessauthorization;
            DROP FUNCTION IF EXISTS gecc_temporary_project_access_insert_guard();
        """)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0048_temporaryprojectaccessauthorization"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]
