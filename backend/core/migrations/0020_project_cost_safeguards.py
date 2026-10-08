"""Database safeguards for GECC Project Cost Records."""

from django.db import migrations


COST_COLUMNS = (
    "equipment_cost",
    "material_cost",
    "dealer_fee",
    "technician_cost",
    "lead_cost",
    "damon_cost",
    "jerry_cost",
)


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER gecc_project_cost_insert_guard
            BEFORE INSERT ON core_projectcostrecord
            BEGIN
                SELECT CASE WHEN
                    NEW.status != 'DRAFT'
                    OR NEW.approved_by_id IS NOT NULL
                    OR NEW.approved_at IS NOT NULL
                    OR NEW.version < 1
                THEN RAISE(ABORT, 'Invalid project cost creation')
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_project_cost_update_guard
            BEFORE UPDATE ON core_projectcostrecord
            BEGIN
                SELECT CASE WHEN OLD.status = 'APPROVED'
                THEN RAISE(ABORT, 'Approved project costs are immutable')
                END;

                SELECT CASE WHEN
                    NEW.status NOT IN ('DRAFT', 'APPROVED')
                    OR NEW.version < 1
                THEN RAISE(ABORT, 'Invalid project cost state')
                END;

                SELECT CASE WHEN NEW.status = 'APPROVED' AND (
                    OLD.status != 'DRAFT'
                    OR NEW.approved_by_id IS NULL
                    OR NEW.approved_at IS NULL
                    OR NEW.project_id != OLD.project_id
                    OR NEW.msr_id != OLD.msr_id
                    OR NEW.version != OLD.version
                    OR NOT EXISTS (
                        SELECT 1 FROM core_user
                        WHERE id = NEW.approved_by_id
                          AND role = 'COMPTROLLER'
                          AND is_active = 1
                    )
                    OR NOT EXISTS (
                        SELECT 1 FROM core_msr
                        WHERE id = NEW.msr_id
                          AND project_id = NEW.project_id
                          AND status = 'APPROVED'
                    )
                    OR NOT EXISTS (
                        SELECT 1 FROM core_project
                        WHERE id = NEW.project_id
                          AND current_approved_id = NEW.msr_id
                    )
                )
                THEN RAISE(ABORT, 'Invalid project cost approval')
                END;
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_project_cost_delete_guard
            BEFORE DELETE ON core_projectcostrecord
            WHEN OLD.status = 'APPROVED'
            BEGIN
                SELECT RAISE(
                    ABORT, 'Approved project costs cannot be deleted'
                );
            END
        """)

        checks = " OR ".join(
            f"NEW.{field} < 0 OR NEW.{field} IS NULL"
            for field in COST_COLUMNS
        )

        for operation in ("INSERT", "UPDATE"):
            schema_editor.execute(f"""
                CREATE TRIGGER gecc_project_cost_nonnegative_{operation.lower()}
                BEFORE {operation} ON core_projectcostrecord
                WHEN {checks}
                BEGIN
                    SELECT RAISE(
                        ABORT, 'Project costs must be nonnegative'
                    );
                END
            """)

        unchanged = " OR ".join(
            f"NEW.{field} != OLD.{field}"
            for field in COST_COLUMNS
        )

        schema_editor.execute(f"""
            CREATE TRIGGER gecc_project_cost_approval_values
            BEFORE UPDATE ON core_projectcostrecord
            WHEN NEW.status = 'APPROVED' AND ({unchanged})
            BEGIN
                SELECT RAISE(
                    ABORT, 'Cost values cannot change during approval'
                );
            END
        """)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_project_cost_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION
                            'Approved project costs cannot be deleted';
                    END IF;
                    RETURN OLD;
                END IF;

                IF TG_OP = 'INSERT' THEN
                    IF NEW.status <> 'DRAFT'
                       OR NEW.approved_by_id IS NOT NULL
                       OR NEW.approved_at IS NOT NULL
                       OR NEW.version < 1 THEN
                        RAISE EXCEPTION 'Invalid project cost creation';
                    END IF;
                ELSE
                    IF OLD.status = 'APPROVED' THEN
                        RAISE EXCEPTION
                            'Approved project costs are immutable';
                    END IF;

                    IF NEW.status NOT IN ('DRAFT', 'APPROVED')
                       OR NEW.version < 1 THEN
                        RAISE EXCEPTION 'Invalid project cost state';
                    END IF;

                    IF NEW.status = 'APPROVED' THEN
                        IF OLD.status <> 'DRAFT'
                           OR NEW.approved_by_id IS NULL
                           OR NEW.approved_at IS NULL
                           OR NEW.project_id <> OLD.project_id
                           OR NEW.msr_id <> OLD.msr_id
                           OR NEW.version <> OLD.version
                           OR NOT EXISTS (
                               SELECT 1 FROM core_user
                               WHERE id = NEW.approved_by_id
                                 AND role = 'COMPTROLLER'
                                 AND is_active = TRUE
                           )
                           OR NOT EXISTS (
                               SELECT 1 FROM core_msr
                               WHERE id = NEW.msr_id
                                 AND project_id = NEW.project_id
                                 AND status = 'APPROVED'
                           )
                           OR NOT EXISTS (
                               SELECT 1 FROM core_project
                               WHERE id = NEW.project_id
                                 AND current_approved_id = NEW.msr_id
                           )
                        THEN
                            RAISE EXCEPTION 'Invalid project cost approval';
                        END IF;

                        IF ROW(
                            NEW.equipment_cost, NEW.material_cost,
                            NEW.dealer_fee, NEW.technician_cost,
                            NEW.lead_cost, NEW.damon_cost, NEW.jerry_cost
                        ) IS DISTINCT FROM ROW(
                            OLD.equipment_cost, OLD.material_cost,
                            OLD.dealer_fee, OLD.technician_cost,
                            OLD.lead_cost, OLD.damon_cost, OLD.jerry_cost
                        ) THEN
                            RAISE EXCEPTION
                                'Cost values cannot change during approval';
                        END IF;
                    END IF;
                END IF;

                IF NEW.equipment_cost < 0
                   OR NEW.material_cost < 0
                   OR NEW.dealer_fee < 0
                   OR NEW.technician_cost < 0
                   OR NEW.lead_cost < 0
                   OR NEW.damon_cost < 0
                   OR NEW.jerry_cost < 0 THEN
                    RAISE EXCEPTION 'Project costs must be nonnegative';
                END IF;

                RETURN NEW;
            END $$;
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_project_cost_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON core_projectcostrecord
            FOR EACH ROW
            EXECUTE FUNCTION gecc_project_cost_guard();
        """)


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        names = [
            "gecc_project_cost_insert_guard",
            "gecc_project_cost_update_guard",
            "gecc_project_cost_delete_guard",
            "gecc_project_cost_nonnegative_insert",
            "gecc_project_cost_nonnegative_update",
            "gecc_project_cost_approval_values",
        ]
        for name in names:
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {name}")

    elif vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS gecc_project_cost_guard
            ON core_projectcostrecord;
        """)
        schema_editor.execute("""
            DROP FUNCTION IF EXISTS gecc_project_cost_guard();
        """)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0019_projectcostrecord"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]
