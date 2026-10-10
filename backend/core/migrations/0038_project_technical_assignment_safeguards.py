from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":

        schema_editor.execute("""
            CREATE TRIGGER gecc_project_technical_assignment_guard
            BEFORE UPDATE ON core_projecttechnicalassignment
            BEGIN

                SELECT CASE WHEN
                    OLD.status = 'ENDED'
                    AND NEW.status != 'ENDED'
                THEN RAISE(
                    ABORT,
                    'Ended technical assignments cannot be reopened'
                )
                END;

            END;
        """)

    elif vendor == "postgresql":

        schema_editor.execute("""
            CREATE FUNCTION gecc_project_technical_assignment_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN

                IF OLD.status = 'ENDED'
                AND NEW.status <> 'ENDED' THEN
                    RAISE EXCEPTION
                    'Ended technical assignments cannot be reopened';
                END IF;

                RETURN NEW;

            END $$;

            CREATE TRIGGER gecc_project_technical_assignment_guard
            BEFORE UPDATE
            ON core_projecttechnicalassignment
            FOR EACH ROW
            EXECUTE FUNCTION gecc_project_technical_assignment_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute(
            """
            DROP TRIGGER IF EXISTS gecc_project_technical_assignment_guard;
            """
        )

    elif vendor == "postgresql":
        schema_editor.execute(
            """
            DROP TRIGGER IF EXISTS gecc_project_technical_assignment_guard
            ON core_projecttechnicalassignment;

            DROP FUNCTION IF EXISTS gecc_project_technical_assignment_guard();
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0037_projecttechnicalassignment"),
    ]

    operations = [
        migrations.RunPython(
            install,
            uninstall,
        ),
    ]