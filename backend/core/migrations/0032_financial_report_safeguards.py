from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":

        schema_editor.execute("""
            CREATE TRIGGER gecc_financial_report_insert_guard
            BEFORE INSERT ON core_financialreport
            BEGIN
                SELECT CASE WHEN
                    NEW.status != 'DRAFT'
                    OR NEW.approved_by_id IS NOT NULL
                    OR NEW.approved_at IS NOT NULL
                THEN RAISE(
                    ABORT,
                    'New financial reports must be draft'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_financial_report_update_guard
            BEFORE UPDATE ON core_financialreport
            BEGIN
                SELECT CASE WHEN OLD.status = 'APPROVED'
                THEN RAISE(
                    ABORT,
                    'Approved financial reports are immutable'
                )
                END;

                SELECT CASE WHEN
                    NEW.status = 'APPROVED'
                    AND (
                        OLD.status != 'DRAFT'
                        OR NEW.approved_by_id IS NULL
                        OR NEW.approved_at IS NULL
                        OR NEW.kind != OLD.kind
                        OR NEW.period_start != OLD.period_start
                        OR NEW.period_end != OLD.period_end
                        OR NEW.report_snapshot != OLD.report_snapshot
                    )
                THEN RAISE(
                    ABORT,
                    'Invalid financial report approval'
                )
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_financial_report_delete_guard
            BEFORE DELETE ON core_financialreport
            WHEN OLD.status = 'APPROVED'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Approved financial reports cannot be deleted'
                );
            END
        """)

    elif vendor == "postgresql":

        schema_editor.execute("""
            CREATE FUNCTION gecc_financial_report_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION
                        'Approved financial reports cannot be deleted';
                    END IF;
                    RETURN OLD;
                END IF;

                IF TG_OP = 'INSERT' THEN
                    IF NEW.status <> 'DRAFT'
                       OR NEW.approved_by_id IS NOT NULL
                       OR NEW.approved_at IS NOT NULL THEN
                        RAISE EXCEPTION
                        'New financial reports must be draft';
                    END IF;
                ELSE
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION
                        'Approved financial reports are immutable';
                    END IF;
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_financial_report_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON core_financialreport
            FOR EACH ROW
            EXECUTE FUNCTION gecc_financial_report_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for name in [
            "gecc_financial_report_insert_guard",
            "gecc_financial_report_update_guard",
            "gecc_financial_report_delete_guard",
        ]:
            schema_editor.execute(
                f"DROP TRIGGER IF EXISTS {name}"
            )

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_financial_report_guard
            ON core_financialreport;

            DROP FUNCTION IF EXISTS gecc_financial_report_guard();
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_financialreport"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]