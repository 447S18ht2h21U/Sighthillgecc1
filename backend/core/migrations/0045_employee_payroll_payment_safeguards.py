from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == 'sqlite':
        schema_editor.execute("""
            CREATE TRIGGER gecc_payroll_issuance_insert_guard
            BEFORE INSERT ON core_employeepayrollpaymentissuance
            BEGIN
                SELECT CASE WHEN NOT EXISTS (
                    SELECT 1 FROM core_employeepayrollrecord p
                    WHERE p.id = NEW.payroll_record_id
                      AND p.status = 'APPROVED'
                      AND p.net_amount = NEW.amount
                )
                THEN RAISE(ABORT, 'Issuance requires approved payroll with matching net amount')
                END;
            END;
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_payroll_issuance_update_guard
            BEFORE UPDATE ON core_employeepayrollpaymentissuance
            BEGIN
                SELECT RAISE(ABORT, 'Payroll issuance evidence is immutable');
            END;
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_payroll_issuance_delete_guard
            BEFORE DELETE ON core_employeepayrollpaymentissuance
            BEGIN
                SELECT RAISE(ABORT, 'Payroll issuance evidence cannot be deleted');
            END;
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_payroll_issuance_settlement_guard
            BEFORE UPDATE ON core_employeepayrollrecord
            WHEN NEW.status = 'PAID' AND OLD.status != 'PAID'
            BEGIN
                SELECT CASE WHEN NOT EXISTS (
                    SELECT 1 FROM core_employeepayrollpaymentissuance i
                    WHERE i.payroll_record_id = NEW.id
                      AND i.amount = NEW.net_amount
                )
                THEN RAISE(ABORT, 'Payment issuance evidence is required before settlement')
                END;
            END;
        """)

    elif vendor == 'postgresql':
        schema_editor.execute("""
            CREATE FUNCTION gecc_payroll_issuance_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'UPDATE' OR TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'Payroll issuance evidence is immutable';
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM core_employeepayrollrecord p
                    WHERE p.id = NEW.payroll_record_id
                      AND p.status = 'APPROVED'
                      AND p.net_amount = NEW.amount
                ) THEN
                    RAISE EXCEPTION 'Issuance requires approved payroll with matching net amount';
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_payroll_issuance_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON core_employeepayrollpaymentissuance
            FOR EACH ROW
            EXECUTE FUNCTION gecc_payroll_issuance_guard();
        """)

        schema_editor.execute("""
            CREATE FUNCTION gecc_payroll_issuance_settlement_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.status = 'PAID' AND OLD.status IS DISTINCT FROM 'PAID' THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM core_employeepayrollpaymentissuance i
                        WHERE i.payroll_record_id = NEW.id
                          AND i.amount = NEW.net_amount
                    ) THEN
                        RAISE EXCEPTION 'Payment issuance evidence is required before settlement';
                    END IF;
                END IF;
                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_payroll_issuance_settlement_guard
            BEFORE UPDATE ON core_employeepayrollrecord
            FOR EACH ROW
            EXECUTE FUNCTION gecc_payroll_issuance_settlement_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == 'sqlite':
        for name in (
            'gecc_payroll_issuance_insert_guard',
            'gecc_payroll_issuance_update_guard',
            'gecc_payroll_issuance_delete_guard',
            'gecc_payroll_issuance_settlement_guard',
        ):
            schema_editor.execute(f'DROP TRIGGER IF EXISTS {name};')

    elif vendor == 'postgresql':
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_payroll_issuance_guard
            ON core_employeepayrollpaymentissuance;
            DROP FUNCTION IF EXISTS gecc_payroll_issuance_guard();

            DROP TRIGGER IF EXISTS gecc_payroll_issuance_settlement_guard
            ON core_employeepayrollrecord;
            DROP FUNCTION IF EXISTS gecc_payroll_issuance_settlement_guard();
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0044_employee_payroll_payment_issuance'),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]
