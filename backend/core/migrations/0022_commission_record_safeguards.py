from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER gecc_commission_insert_guard
            BEFORE INSERT ON core_commissionrecord
            BEGIN
                SELECT CASE WHEN
                    NEW.status != 'DRAFT'
                    OR NEW.approved_by_id IS NOT NULL
                    OR NEW.approved_at IS NOT NULL
                THEN RAISE(
                    ABORT,
                    'New commission records must be draft'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_commission_update_guard
            BEFORE UPDATE ON core_commissionrecord
            BEGIN
                SELECT CASE WHEN OLD.status = 'APPROVED'
                THEN RAISE(
                    ABORT,
                    'Approved commission records are immutable'
                )
                END;

                SELECT CASE WHEN
                    NEW.status = 'APPROVED'
                    AND (
                        OLD.status != 'DRAFT'
                        OR NEW.approved_by_id IS NULL
                        OR NEW.approved_at IS NULL
                        OR NEW.project_id != OLD.project_id
                        OR NEW.msr_id != OLD.msr_id
                        OR NEW.recipient_id != OLD.recipient_id
                        OR NEW.kind != OLD.kind
                        OR NEW.rate != OLD.rate
                        OR NEW.basis_amount != OLD.basis_amount
                        OR NEW.deduction_amount != OLD.deduction_amount
                        OR NEW.final_amount != OLD.final_amount
                        OR NEW.calculation_snapshot != OLD.calculation_snapshot
                    )
                THEN RAISE(
                    ABORT,
                    'Invalid commission approval'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_commission_delete_guard
            BEFORE DELETE ON core_commissionrecord
            WHEN OLD.status = 'APPROVED'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Approved commission records cannot be deleted'
                );
            END
        """)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_commission_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION
                        'Approved commission records cannot be deleted';
                    END IF;
                    RETURN OLD;
                END IF;

                IF TG_OP = 'INSERT' THEN
                    IF NEW.status <> 'DRAFT'
                       OR NEW.approved_by_id IS NOT NULL
                       OR NEW.approved_at IS NOT NULL THEN
                        RAISE EXCEPTION
                        'New commission records must be draft';
                    END IF;
                ELSE
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION
                        'Approved commission records are immutable';
                    END IF;
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_commission_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON core_commissionrecord
            FOR EACH ROW
            EXECUTE FUNCTION gecc_commission_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for name in [
            "gecc_commission_insert_guard",
            "gecc_commission_update_guard",
            "gecc_commission_delete_guard",
        ]:
            schema_editor.execute(
                f"DROP TRIGGER IF EXISTS {name}"
            )

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_commission_guard
            ON core_commissionrecord;

            DROP FUNCTION IF EXISTS gecc_commission_guard();
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0021_commissionrecord"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]