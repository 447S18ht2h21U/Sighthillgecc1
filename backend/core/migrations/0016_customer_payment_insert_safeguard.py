from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER gecc_customer_payment_insert_guard
            BEFORE INSERT ON core_customerpayment
            WHEN NEW.status != 'PENDING'
                 OR NEW.verified_by_id IS NOT NULL
                 OR NEW.verified_at IS NOT NULL
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'New customer payments must be pending'
                );
            END
        """)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_customer_payment_insert_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.status IS DISTINCT FROM 'PENDING'
                   OR NEW.verified_by_id IS NOT NULL
                   OR NEW.verified_at IS NOT NULL
                THEN
                    RAISE EXCEPTION
                        'New customer payments must be pending';
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_customer_payment_insert_guard
            BEFORE INSERT ON core_customerpayment
            FOR EACH ROW
            EXECUTE FUNCTION gecc_customer_payment_insert_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS
            gecc_customer_payment_insert_guard
        """)

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS
            gecc_customer_payment_insert_guard
            ON core_customerpayment;

            DROP FUNCTION IF EXISTS
            gecc_customer_payment_insert_guard();
        """)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0015_customer_payment_safeguards"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]