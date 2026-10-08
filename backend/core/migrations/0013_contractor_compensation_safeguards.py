from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        statements = [
            """
            CREATE TRIGGER gecc_compensation_plan_immutable
            BEFORE UPDATE ON core_contractorcompensationplan
            WHEN OLD.status = 'APPROVED'
            BEGIN
                SELECT RAISE(ABORT, 'Approved compensation plan is immutable');
            END
            """,
            """
            CREATE TRIGGER gecc_compensation_plan_delete
            BEFORE DELETE ON core_contractorcompensationplan
            WHEN OLD.status = 'APPROVED'
            BEGIN
                SELECT RAISE(ABORT, 'Approved compensation plan cannot be deleted');
            END
            """,
            """
            CREATE TRIGGER gecc_compensation_plan_approval
            BEFORE UPDATE ON core_contractorcompensationplan
            WHEN NEW.status = 'APPROVED'
            BEGIN
                SELECT CASE WHEN
                    OLD.status != 'DRAFT'
                    OR NEW.approved_by_id IS NULL
                    OR NEW.approved_at IS NULL
                    OR NEW.compensation_terms IS NULL
                    OR NEW.compensation_terms = '{}'
                    OR NOT EXISTS (
                        SELECT 1 FROM core_user
                        WHERE id = NEW.approved_by_id
                        AND role = 'COMPTROLLER'
                        AND is_active = 1
                    )
                    OR NOT EXISTS (
                        SELECT 1 FROM core_contractorengagement
                        WHERE id = NEW.engagement_id
                        AND status = 'ACTIVE'
                    )
                THEN RAISE(ABORT, 'Invalid compensation plan approval')
                END;
            END
            """,
        ]
        for statement in statements:
            schema_editor.execute(statement)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_compensation_plan_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION 'Approved compensation plan cannot be deleted';
                    END IF;
                    RETURN OLD;
                END IF;

                IF OLD.status = 'APPROVED' THEN
                    RAISE EXCEPTION 'Approved compensation plan is immutable';
                END IF;

                IF NEW.status = 'APPROVED' THEN
                    IF OLD.status <> 'DRAFT'
                       OR NEW.approved_by_id IS NULL
                       OR NEW.approved_at IS NULL
                       OR NEW.compensation_terms IS NULL
                       OR NEW.compensation_terms = '{}'::jsonb
                       OR NOT EXISTS (
                           SELECT 1 FROM core_user
                           WHERE id = NEW.approved_by_id
                           AND role = 'COMPTROLLER'
                           AND is_active = TRUE
                       )
                       OR NOT EXISTS (
                           SELECT 1 FROM core_contractorengagement
                           WHERE id = NEW.engagement_id
                           AND status = 'ACTIVE'
                       )
                    THEN
                        RAISE EXCEPTION 'Invalid compensation plan approval';
                    END IF;
                END IF;

                RETURN NEW;
            END $$;

                        CREATE TRIGGER gecc_compensation_plan_guard
            BEFORE UPDATE OR DELETE
            ON core_contractorcompensationplan
            FOR EACH ROW
            EXECUTE FUNCTION gecc_compensation_plan_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for name in [
            "gecc_compensation_plan_immutable",
            "gecc_compensation_plan_delete",
            "gecc_compensation_plan_approval",
        ]:
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {name}")

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_compensation_plan_guard
            ON core_contractorcompensationplan;
            DROP FUNCTION IF EXISTS gecc_compensation_plan_guard();
        """)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_contractorcompensationplan"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_contractorcompensationplan"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]

