"""Database integrity safeguards for customer payment bank confirmations."""

from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER gecc_bank_confirmation_insert_guard
            BEFORE INSERT ON core_customerpaymentbankconfirmation
            BEGIN
                SELECT CASE WHEN
                    TRIM(COALESCE(NEW.bank_reference, '')) = ''
                    OR TRIM(COALESCE(NEW.confirmation_method, '')) = ''
                    OR TRIM(COALESCE(NEW.confirmation_note, '')) = ''
                    OR NEW.confirmation_date IS NULL
                    OR NEW.confirmed_at IS NULL
                    OR NOT EXISTS (
                        SELECT 1 FROM core_user u
                        WHERE u.id = NEW.confirmed_by_id
                          AND u.role = 'COMPTROLLER'
                          AND u.is_active = 1
                    )
                    OR NOT EXISTS (
                        SELECT 1
                        FROM core_customerpayment cp
                        JOIN core_msr m ON m.id = cp.msr_id
                        JOIN core_project p ON p.id = cp.project_id
                        WHERE cp.id = NEW.payment_id
                          AND cp.status = 'VERIFIED'
                          AND cp.amount > 0
                          AND cp.verified_by_id IS NOT NULL
                          AND cp.verified_at IS NOT NULL
                          AND cp.project_id = m.project_id
                          AND m.project_id = p.id
                          AND m.status = 'APPROVED'
                          AND NEW.confirmation_date >= cp.received_date
                          AND NEW.confirmed_at >= cp.verified_at
                    )
                THEN RAISE(
                    ABORT,
                    'Invalid customer payment bank confirmation'
                )
                END;
            END;
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_bank_confirmation_update_guard
            BEFORE UPDATE ON core_customerpaymentbankconfirmation
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Bank confirmation is immutable'
                );
            END;
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_bank_confirmation_delete_guard
            BEFORE DELETE ON core_customerpaymentbankconfirmation
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Bank confirmation cannot be deleted'
                );
            END;
        """)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_bank_confirmation_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION
                        'Bank confirmation cannot be deleted';
                END IF;

                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION
                        'Bank confirmation is immutable';
                END IF;

                IF TG_OP = 'INSERT' THEN
                    IF BTRIM(COALESCE(NEW.bank_reference, '')) = ''
                       OR BTRIM(COALESCE(NEW.confirmation_method, '')) = ''
                       OR BTRIM(COALESCE(NEW.confirmation_note, '')) = ''
                       OR NEW.confirmation_date IS NULL
                       OR NEW.confirmed_at IS NULL
                       OR NOT EXISTS (
                           SELECT 1 FROM core_user u
                           WHERE u.id = NEW.confirmed_by_id
                             AND u.role = 'COMPTROLLER'
                             AND u.is_active = TRUE
                       )
                       OR NOT EXISTS (
                           SELECT 1
                           FROM core_customerpayment cp
                           JOIN core_msr m ON m.id = cp.msr_id
                           JOIN core_project p ON p.id = cp.project_id
                           WHERE cp.id = NEW.payment_id
                             AND cp.status = 'VERIFIED'
                             AND cp.amount > 0
                             AND cp.verified_by_id IS NOT NULL
                             AND cp.verified_at IS NOT NULL
                             AND cp.project_id = m.project_id
                             AND m.project_id = p.id
                             AND m.status = 'APPROVED'
                             AND NEW.confirmation_date >= cp.received_date
                             AND NEW.confirmed_at >= cp.verified_at
                       )
                    THEN
                        RAISE EXCEPTION
                            'Invalid customer payment bank confirmation';
                    END IF;

                    RETURN NEW;
                END IF;

                RAISE EXCEPTION 'Unsupported bank confirmation operation';
            END $$;
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_bank_confirmation_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON core_customerpaymentbankconfirmation
            FOR EACH ROW
            EXECUTE FUNCTION gecc_bank_confirmation_guard();
        """)

    else:
        raise RuntimeError(
            "SAFETY STOP: Unsupported database engine."
        )


def uninstall(apps, schema_editor):
    raise RuntimeError(
        "SAFETY STOP: Bank confirmation safeguards require controlled removal."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0065_customerpaymentbankconfirmation"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]
