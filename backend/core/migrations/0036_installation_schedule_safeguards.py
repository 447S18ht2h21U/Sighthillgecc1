from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":

        schema_editor.execute("""
            CREATE TRIGGER gecc_installation_schedule_guard
            BEFORE UPDATE ON core_installationschedule
            BEGIN

                SELECT CASE WHEN
                    OLD.status = 'COMPLETED'
                    AND NEW.status != 'COMPLETED'
                THEN RAISE(
                    ABORT,
                    'Completed installations cannot be reopened'
                )
                END;

                SELECT CASE WHEN
                    OLD.status = 'CANCELLED'
                    AND NEW.status != 'CANCELLED'
                THEN RAISE(
                    ABORT,
                    'Cancelled installations cannot be reopened'
                )
                END;

            END;
        """)

    elif vendor == "postgresql":

        schema_editor.execute("""
            CREATE FUNCTION gecc_installation_schedule_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN

                IF OLD.status = 'COMPLETED'
                AND NEW.status <> 'COMPLETED' THEN
                    RAISE EXCEPTION
                    'Completed installations cannot be reopened';
                END IF;

                IF OLD.status = 'CANCELLED'
                AND NEW.status <> 'CANCELLED' THEN
                    RAISE EXCEPTION
                    'Cancelled installations cannot be reopened';
                END IF;

                RETURN NEW;

            END $$;

            CREATE TRIGGER gecc_installation_schedule_guard
            BEFORE UPDATE
            ON core_installationschedule
            FOR EACH ROW
            EXECUTE FUNCTION gecc_installation_schedule_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute(
            """
            DROP TRIGGER IF EXISTS gecc_installation_schedule_guard;
            """
        )

    elif vendor == "postgresql":
        schema_editor.execute(
            """
            DROP TRIGGER IF EXISTS gecc_installation_schedule_guard
            ON core_installationschedule;

            DROP FUNCTION IF EXISTS gecc_installation_schedule_guard();
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_installationschedule"),
    ]

    operations = [
        migrations.RunPython(
            install,
            uninstall,
        ),
    ]