from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        statements = [
            """
            CREATE TRIGGER gecc_customer_payment_immutable
            BEFORE UPDATE ON core_customerpayment
            WHEN OLD.status = 'VERIFIED'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Verified customer payment is immutable'
                );
            END
            """,
            """
            CREATE TRIGGER gecc_customer_payment_delete
            BEFORE DELETE ON core_customerpayment
            WHEN OLD.status = 'VERIFIED'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Verified customer payment cannot be deleted'
                );
            END
            """,
            """
            CREATE TRIGGER gecc_customer_payment_verify
            BEFORE UPDATE ON core_customerpayment
            WHEN NEW.status = 'VERIFIED'
            BEGIN
                SELECT CASE WHEN
                    OLD.status != 'PENDING'
                    OR NEW.verified_by_id IS NULL
                    OR NEW.verified_at IS NULL
                    OR NEW.amount <= 0
                    OR TRIM(NEW.payment_reference) = ''
                    OR NOT EXISTS (
                        SELECT 1 FROM core_user
                        WHERE id = NEW.verified_by_id
                        AND role = 'COMPTROLLER'
                        AND is_active = 1
                    )
                    OR NOT EXISTS (
                        SELECT 1 FROM core_project p
                        JOIN core_msr m
                          ON m.id = NEW.msr_id
                        WHERE p.id = NEW.project_id
                          AND p.current_approved_id = m.id
                          AND p.state != 'CANCELLED'
                          AND m.project_id = p.id
                          AND m.status = 'APPROVED'
                    )
                    OR EXISTS (
                        SELECT 1 FROM core_customerpayment other
                        WHERE other.project_id = NEW.project_id
                          AND other.payment_reference =
                              NEW.payment_reference
                          AND other.status = 'VERIFIED'
                          AND other.id != NEW.id
                    )
                THEN RAISE(
                    ABORT,
                    'Invalid customer payment verification'
                )
                END;
            END
            """,
        ]

        for statement in statements:
            schema_editor.execute(statement)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_customer_payment_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status = 'VERIFIED' THEN
                        RAISE EXCEPTION
                            'Verified customer payment cannot be deleted';
                    END IF;
                    RETURN OLD;
                END IF;

                IF OLD.status = 'VERIFIED' THEN
                    RAISE EXCEPTION
                        'Verified customer payment is immutable';
                END IF;

                IF NEW.status = 'VERIFIED' THEN
                    IF OLD.status <> 'PENDING'
                       OR NEW.verified_by_id IS NULL
                       OR NEW.verified_at IS NULL
                       OR NEW.amount <= 0
                       OR BTRIM(NEW.payment_reference) = ''
                       OR NOT EXISTS (
                           SELECT 1 FROM core_user
                           WHERE id = NEW.verified_by_id
                             AND role = 'COMPTROLLER'
                             AND is_active = TRUE
                       )
                       OR NOT EXISTS (
                           SELECT 1
                           FROM core_project p
                           JOIN core_msr m
                             ON m.id = NEW.msr_id
                           WHERE p.id = NEW.project_id
                             AND p.current_approved_id = m.id
                             AND p.state <> 'CANCELLED'
                             AND m.project_id = p.id
                             AND m.status = 'APPROVED'
                       )
                       OR EXISTS (
                           SELECT 1 FROM core_customerpayment other
                           WHERE other.project_id = NEW.project_id
                             AND other.payment_reference =
                                 NEW.payment_reference
                             AND other.status = 'VERIFIED'
                             AND other.id <> NEW.id
                       )
                    THEN
                        RAISE EXCEPTION
                            'Invalid customer payment verification';
                    END IF;
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_customer_payment_guard
            BEFORE UPDATE OR DELETE
            ON core_customerpayment
            FOR EACH ROW
            EXECUTE FUNCTION gecc_customer_payment_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for name in [
            "gecc_customer_payment_immutable",
            "gecc_customer_payment_delete",
            "gecc_customer_payment_verify",
        ]:
            schema_editor.execute(
                f"DROP TRIGGER IF EXISTS {name}"
            )

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_customer_payment_guard
            ON core_customerpayment;

            DROP FUNCTION IF EXISTS gecc_customer_payment_guard();
        """)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_customerpayment"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]