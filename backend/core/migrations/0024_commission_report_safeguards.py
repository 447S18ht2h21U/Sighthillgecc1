from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER gecc_commission_report_insert_guard
            BEFORE INSERT ON core_commissionreport
            BEGIN
                SELECT CASE WHEN
                    NEW.status != 'DRAFT'
                    OR NEW.approved_by_id IS NOT NULL
                    OR NEW.approved_at IS NOT NULL
                THEN RAISE(
                    ABORT,
                    'New commission reports must be draft'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_commission_report_update_guard
            BEFORE UPDATE ON core_commissionreport
            BEGIN
                SELECT CASE WHEN OLD.status = 'APPROVED'
                THEN RAISE(
                    ABORT,
                    'Approved commission reports are immutable'
                )
                END;

                SELECT CASE WHEN
                    NEW.status = 'APPROVED'
                    AND (
                        OLD.status != 'DRAFT'
                        OR NEW.approved_by_id IS NULL
                        OR NEW.approved_at IS NULL
                        OR NEW.period_start != OLD.period_start
                        OR NEW.period_end != OLD.period_end
                        OR NEW.report_snapshot != OLD.report_snapshot
                    )
                THEN RAISE(
                    ABORT,
                    'Invalid commission report approval'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_commission_report_delete_guard
            BEFORE DELETE ON core_commissionreport
            WHEN OLD.status = 'APPROVED'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Approved commission reports cannot be deleted'
                );
            END
        """)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_commission_report_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION
                        'Approved commission reports cannot be deleted';
                    END IF;
                    RETURN OLD;
                END IF;

                IF TG_OP = 'INSERT' THEN
                    IF NEW.status <> 'DRAFT'
                       OR NEW.approved_by_id IS NOT NULL
                       OR NEW.approved_at IS NOT NULL THEN
                        RAISE EXCEPTION
                        'New commission reports must be draft';
                    END IF;
                ELSE
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION
                        'Approved commission reports are immutable';
                    END IF;
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_commission_report_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON core_commissionreport
            FOR EACH ROW
            EXECUTE FUNCTION gecc_commission_report_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for name in [
            "gecc_commission_report_insert_guard",
            "gecc_commission_report_update_guard",
            "gecc_commission_report_delete_guard",
        ]:
            schema_editor.execute(
                f"DROP TRIGGER IF EXISTS {name}"
            )

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_commission_report_guard
            ON core_commissionreport;

            DROP FUNCTION IF EXISTS gecc_commission_report_guard();
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0023_commissionreport"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]