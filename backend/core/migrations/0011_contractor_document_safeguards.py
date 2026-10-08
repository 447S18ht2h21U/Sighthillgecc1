from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        statements = [
            """
            CREATE TRIGGER gecc_contractor_document_immutable
            BEFORE UPDATE ON core_contractoronboardingdocument
            WHEN OLD.status = 'APPROVED'
            BEGIN
                SELECT RAISE(ABORT, 'Approved contractor document is immutable');
            END
            """,
            """
            CREATE TRIGGER gecc_contractor_document_delete
            BEFORE DELETE ON core_contractoronboardingdocument
            WHEN OLD.status = 'APPROVED'
            BEGIN
                SELECT RAISE(ABORT, 'Approved contractor document cannot be deleted');
            END
            """,
            """
            CREATE TRIGGER gecc_contractor_document_approval
            BEFORE UPDATE ON core_contractoronboardingdocument
            WHEN NEW.status = 'APPROVED'
            BEGIN
                SELECT CASE WHEN
                    OLD.status != 'PENDING'
                    OR NEW.reviewed_by_id IS NULL
                    OR NEW.reviewed_at IS NULL
                    OR TRIM(NEW.storage_reference) = ''
                    OR NOT EXISTS (
                        SELECT 1 FROM core_user
                        WHERE id = NEW.reviewed_by_id
                        AND role = 'COMPTROLLER'
                        AND is_active = 1
                    )
                THEN RAISE(ABORT, 'Invalid contractor document approval')
                END;
            END
            """,
        ]
        for statement in statements:
            schema_editor.execute(statement)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_contractor_document_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION 'Approved contractor document cannot be deleted';
                    END IF;
                    RETURN OLD;
                END IF;

                IF OLD.status = 'APPROVED' THEN
                    RAISE EXCEPTION 'Approved contractor document is immutable';
                END IF;

                IF NEW.status = 'APPROVED' THEN
                    IF OLD.status <> 'PENDING'
                       OR NEW.reviewed_by_id IS NULL
                       OR NEW.reviewed_at IS NULL
                       OR BTRIM(NEW.storage_reference) = ''
                       OR NOT EXISTS (
                           SELECT 1 FROM core_user
                           WHERE id = NEW.reviewed_by_id
                           AND role = 'COMPTROLLER'
                           AND is_active = TRUE
                       )
                    THEN
                        RAISE EXCEPTION 'Invalid contractor document approval';
                    END IF;
                END IF;

                RETURN NEW;
            END $$;

            CREATE TRIGGER gecc_contractor_document_guard
            BEFORE UPDATE OR DELETE
            ON core_contractoronboardingdocument
            FOR EACH ROW
            EXECUTE FUNCTION gecc_contractor_document_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        for name in [
            "gecc_contractor_document_immutable",
            "gecc_contractor_document_delete",
            "gecc_contractor_document_approval",
        ]:
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {name}")

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_contractor_document_guard
            ON core_contractoronboardingdocument;
            DROP FUNCTION IF EXISTS gecc_contractor_document_guard();
        """)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_contractor_contractorengagement_and_more"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]
