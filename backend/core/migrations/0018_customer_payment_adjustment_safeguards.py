from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        statements = [
            """
            CREATE TRIGGER gecc_adjustment_insert_guard
            BEFORE INSERT ON core_customerpaymentadjustment
            WHEN NEW.status != 'PENDING'
                 OR NEW.approved_by_id IS NOT NULL
                 OR NEW.approved_at IS NOT NULL
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'New payment adjustments must be pending'
                );
            END
            """,
            """
            CREATE TRIGGER gecc_adjustment_immutable
            BEFORE UPDATE ON core_customerpaymentadjustment
            WHEN OLD.status = 'APPROVED'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Approved payment adjustment is immutable'
                );
            END
            """,
            """
            CREATE TRIGGER gecc_adjustment_delete
            BEFORE DELETE ON core_customerpaymentadjustment
            WHEN OLD.status = 'APPROVED'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Approved payment adjustment cannot be deleted'
                );
            END
            """,
            """
            CREATE TRIGGER gecc_adjustment_approve
            BEFORE UPDATE ON core_customerpaymentadjustment
            WHEN NEW.status = 'APPROVED'
            BEGIN
                SELECT CASE WHEN
                    OLD.status != 'PENDING'
                    OR NEW.approved_by_id IS NULL
                    OR NEW.approved_at IS NULL
                    OR NEW.amount <= 0
                    OR TRIM(NEW.adjustment_reference) = ''
                    OR TRIM(NEW.reason) = ''
                    OR NEW.payment_id != OLD.payment_id
                    OR NEW.kind != OLD.kind
                    OR NEW.amount != OLD.amount
                    OR NEW.adjustment_date != OLD.adjustment_date
                    OR NEW.adjustment_reference != OLD.adjustment_reference
                    OR NEW.reason != OLD.reason
                    OR NEW.recorded_by_id != OLD.recorded_by_id
                    OR NOT EXISTS (
                        SELECT 1 FROM core_user
                        WHERE id = NEW.approved_by_id
                          AND role = 'COMPTROLLER'
                          AND is_active = 1
                    )
                    OR NOT EXISTS (
                        SELECT 1 FROM core_customerpayment
                        WHERE id = NEW.payment_id
                          AND status = 'VERIFIED'
                    )
                    OR (
                        COALESCE((
                            SELECT SUM(amount)
                            FROM core_customerpaymentadjustment
                            WHERE payment_id = NEW.payment_id
                              AND status = 'APPROVED'
                              AND id != NEW.id
                        ), 0) + NEW.amount
                    ) > (
                        SELECT amount
                        FROM core_customerpayment
                        WHERE id = NEW.payment_id
                    )
                THEN RAISE(
                    ABORT,
                    'Invalid payment adjustment approval'
                )
                END;
            END
            """,
        ]

        for statement in statements:
            schema_editor.execute(statement)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_adjustment_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    IF NEW.status IS DISTINCT FROM 'PENDING'
                       OR NEW.approved_by_id IS NOT NULL
                       OR NEW.approved_at IS NOT NULL
                    THEN
                        RAISE EXCEPTION
                            'New payment adjustments must be pending';
                    END IF;

                    RETURN NEW;
                END IF;

                IF TG_OP = 'DELETE' THEN
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION
                            'Approved payment adjustment cannot be deleted';
                    END IF;

                    RETURN OLD;
                END IF;

                IF OLD.status = 'APPROVED' THEN
                    RAISE EXCEPTION
                        'Approved payment adjustment is immutable';
                END IF;

                IF NEW.status = 'APPROVED' THEN
                    IF OLD.status <> 'PENDING'
                       OR NEW.approved_by_id IS NULL
                       OR NEW.approved_at IS NULL
                       OR NEW.amount <= 0
                       OR BTRIM(NEW.adjustment_reference) = ''
                       OR BTRIM(NEW.reason) = ''
                       OR NEW.payment_id IS DISTINCT FROM OLD.payment_id
                       OR NEW.kind IS DISTINCT FROM OLD.kind
                       OR NEW.amount IS DISTINCT FROM OLD.amount
                       OR NEW.adjustment_date IS DISTINCT FROM OLD.adjustment_date
                       OR NEW.adjustment_reference IS DISTINCT FROM OLD.adjustment_reference
                       OR NEW.reason IS DISTINCT FROM OLD.reason
                       OR NEW.recorded_by_id IS DISTINCT FROM OLD.recorded_by_id
                       OR NOT EXISTS (
                           SELECT 1 FROM core_user
                           WHERE id = NEW.approved_by_id
                             AND role = 'COMPTROLLER'
                             AND is_active = TRUE
                       )
                       OR NOT EXISTS (
                           SELECT 1 FROM core_customerpayment
                           WHERE id = NEW.payment_id
                             AND status = 'VERIFIED'
                       )
                       OR (
                           COALESCE((
                               SELECT SUM(amount)
                               FROM core_customerpaymentadjustment
                               WHERE payment_id = NEW.payment_id
                                 AND status = 'APPROVED'
                                 AND id <> NEW.id
                           ), 0) + NEW.amount
                       ) > (
                           SELECT amount
                           FROM core_customerpayment
                           WHERE id = NEW.payment_id
                       )
                    THEN
                        RAISE EXCEPTION
                            'Invalid payment adjustment approval';
                    END IF;
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_adjustment_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON core_customerpaymentadjustment
            FOR EACH ROW
            EXECUTE FUNCTION gecc_adjustment_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for name in [
            "gecc_adjustment_insert_guard",
            "gecc_adjustment_immutable",
            "gecc_adjustment_delete",
            "gecc_adjustment_approve",
        ]:
            schema_editor.execute(
                f"DROP TRIGGER IF EXISTS {name}"
            )

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_adjustment_guard
            ON core_customerpaymentadjustment;

            DROP FUNCTION IF EXISTS gecc_adjustment_guard();
        """)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0017_customerpaymentadjustment"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]