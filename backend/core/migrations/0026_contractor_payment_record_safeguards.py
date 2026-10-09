from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":

        schema_editor.execute("""
            CREATE TRIGGER gecc_contractor_payment_insert_guard
            BEFORE INSERT ON core_contractorpaymentrecord
            BEGIN
                SELECT CASE WHEN
                    NEW.status != 'DRAFT'
                    OR NEW.approved_by_id IS NOT NULL
                    OR NEW.approved_at IS NOT NULL
                    OR NEW.paid_at IS NOT NULL
                THEN RAISE(
                    ABORT,
                    'New contractor payments must be draft'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_contractor_payment_update_guard
            BEFORE UPDATE ON core_contractorpaymentrecord
            BEGIN
                SELECT CASE WHEN OLD.status = 'PAID'
                THEN RAISE(
                    ABORT,
                    'Paid contractor payments are immutable'
                )
                END;

                SELECT CASE WHEN OLD.status = 'APPROVED'
                    AND (
                        NEW.engagement_id != OLD.engagement_id
                        OR NEW.compensation_plan_id != OLD.compensation_plan_id
                        OR NEW.project_id != OLD.project_id
                        OR NEW.kind != OLD.kind
                        OR NEW.basis_amount != OLD.basis_amount
                        OR NEW.deduction_amount != OLD.deduction_amount
                        OR NEW.final_amount != OLD.final_amount
                        OR NEW.calculation_snapshot != OLD.calculation_snapshot
                    )
                THEN RAISE(
                    ABORT,
                    'Approved contractor payments cannot change'
                )
                END;

                SELECT CASE WHEN
                    NEW.status = 'APPROVED'
                    AND (
                        OLD.status != 'DRAFT'
                        OR NEW.approved_by_id IS NULL
                        OR NEW.approved_at IS NULL
                    )
                THEN RAISE(
                    ABORT,
                    'Invalid contractor payment approval'
                )
                END;

                SELECT CASE WHEN
                    NEW.status = 'PAID'
                    AND (
                        OLD.status != 'APPROVED'
                        OR NEW.paid_at IS NULL
                    )
                THEN RAISE(
                    ABORT,
                    'Invalid contractor payment settlement'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_contractor_payment_delete_guard
            BEFORE DELETE ON core_contractorpaymentrecord
            WHEN OLD.status IN ('APPROVED', 'PAID')
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Approved or paid contractor payments cannot be deleted'
                );
            END
        """)

    elif vendor == "postgresql":

        schema_editor.execute("""
            CREATE FUNCTION gecc_contractor_payment_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status IN ('APPROVED','PAID') THEN
                        RAISE EXCEPTION
                        'Approved or paid contractor payments cannot be deleted';
                    END IF;
                    RETURN OLD;
                END IF;

                IF TG_OP = 'INSERT' THEN
                    IF NEW.status <> 'DRAFT'
                       OR NEW.approved_by_id IS NOT NULL
                       OR NEW.approved_at IS NOT NULL
                       OR NEW.paid_at IS NOT NULL THEN
                        RAISE EXCEPTION
                        'New contractor payments must be draft';
                    END IF;
                ELSE
                    IF OLD.status = 'PAID' THEN
                        RAISE EXCEPTION
                        'Paid contractor payments are immutable';
                    END IF;
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_contractor_payment_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON core_contractorpaymentrecord
            FOR EACH ROW
            EXECUTE FUNCTION gecc_contractor_payment_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for name in [
            "gecc_contractor_payment_insert_guard",
            "gecc_contractor_payment_update_guard",
            "gecc_contractor_payment_delete_guard",
        ]:
            schema_editor.execute(
                f"DROP TRIGGER IF EXISTS {name}"
            )

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_contractor_payment_guard
            ON core_contractorpaymentrecord;

            DROP FUNCTION IF EXISTS gecc_contractor_payment_guard();
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_contractorpaymentrecord"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]