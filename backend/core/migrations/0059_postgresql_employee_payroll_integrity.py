from django.db import migrations


PAYROLL_GUARD_SQL = """
CREATE OR REPLACE FUNCTION gecc_employee_payroll_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status IN ('APPROVED', 'PAID') THEN
            RAISE EXCEPTION 'Approved or paid employee payroll cannot be deleted';
        END IF;
        RETURN OLD;
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'DRAFT'
           OR NEW.approved_by_id IS NOT NULL
           OR NEW.approved_at IS NOT NULL
           OR NEW.paid_at IS NOT NULL THEN
            RAISE EXCEPTION 'New employee payroll records must be draft';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.status = 'DRAFT' AND (
        NEW.approved_by_id IS NOT NULL
        OR NEW.approved_at IS NOT NULL
        OR NEW.paid_at IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'Draft payroll cannot contain approval or payment evidence';
    END IF;
    IF OLD.status = 'PAID' THEN
        RAISE EXCEPTION 'Paid employee payroll records are immutable';
    END IF;

    IF OLD.status IN ('DRAFT', 'APPROVED')
       AND NEW.status IN ('APPROVED', 'PAID') AND (
        NEW.employee_id IS DISTINCT FROM OLD.employee_id
        OR NEW.compensation_plan_id IS DISTINCT FROM OLD.compensation_plan_id
        OR NEW.kind IS DISTINCT FROM OLD.kind
        OR NEW.payroll_period_start IS DISTINCT FROM OLD.payroll_period_start
        OR NEW.payroll_period_end IS DISTINCT FROM OLD.payroll_period_end
        OR NEW.gross_amount IS DISTINCT FROM OLD.gross_amount
        OR NEW.deduction_amount IS DISTINCT FROM OLD.deduction_amount
        OR NEW.net_amount IS DISTINCT FROM OLD.net_amount
        OR NEW.calculation_snapshot IS DISTINCT FROM OLD.calculation_snapshot
        OR NEW.created_by_id IS DISTINCT FROM OLD.created_by_id
        OR NEW.created_at IS DISTINCT FROM OLD.created_at
        OR (
            OLD.status = 'APPROVED'
            AND (
                NEW.approved_by_id IS DISTINCT FROM OLD.approved_by_id
                OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
            )
        )
    ) THEN
        RAISE EXCEPTION 'Approved employee payroll cannot change';
    END IF;

    IF OLD.status = 'APPROVED'
       AND NEW.status NOT IN ('APPROVED', 'PAID') THEN
        RAISE EXCEPTION 'Approved payroll cannot return to draft';
    END IF;
    IF NEW.status = 'APPROVED'
       AND OLD.status <> 'APPROVED' AND (
        OLD.status <> 'DRAFT'
        OR NEW.approved_by_id IS NULL
        OR NEW.approved_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Invalid employee payroll approval';
    END IF;

    IF NEW.status = 'APPROVED'
       AND NEW.paid_at IS NOT NULL THEN
        RAISE EXCEPTION 'Approved payroll cannot contain payment timestamp';
    END IF;
    IF NEW.status = 'PAID' AND (
        OLD.status <> 'APPROVED'
        OR NEW.paid_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Invalid employee payroll settlement';
    END IF;

    RETURN NEW;
END $$;
"""

COMPENSATION_PLAN_GUARD_SQL = """
CREATE FUNCTION gecc_employee_comp_plan_update_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = 'APPROVED' THEN
        RAISE EXCEPTION
            'Approved employee compensation plans are immutable';
    END IF;

    RETURN NEW;
END $$;

CREATE TRIGGER gecc_employee_comp_plan_update_guard
BEFORE UPDATE ON core_employeecompensationplan
FOR EACH ROW
EXECUTE FUNCTION gecc_employee_comp_plan_update_guard();
"""

PAYROLL_ROLLBACK_SQL = """
CREATE OR REPLACE FUNCTION gecc_employee_payroll_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status IN ('APPROVED','PAID') THEN
            RAISE EXCEPTION
            'Approved or paid employee payroll cannot be deleted';
        END IF;
        RETURN OLD;
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'DRAFT'
           OR NEW.approved_by_id IS NOT NULL
           OR NEW.approved_at IS NOT NULL
           OR NEW.paid_at IS NOT NULL THEN
            RAISE EXCEPTION
            'New employee payroll records must be draft';
        END IF;
    ELSE
        IF OLD.status = 'PAID' THEN
            RAISE EXCEPTION
            'Paid employee payroll records are immutable';
        END IF;
    END IF;

    RETURN NEW;
END $$;
"""

COMPENSATION_PLAN_ROLLBACK_SQL = """
DROP TRIGGER IF EXISTS gecc_employee_comp_plan_update_guard
ON core_employeecompensationplan;

DROP FUNCTION IF EXISTS gecc_employee_comp_plan_update_guard();
"""

def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return



    schema_editor.execute(PAYROLL_GUARD_SQL)
    schema_editor.execute(COMPENSATION_PLAN_GUARD_SQL)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return



    schema_editor.execute(COMPENSATION_PLAN_ROLLBACK_SQL)
    schema_editor.execute(PAYROLL_ROLLBACK_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0058_completion_envelope_identity_guards"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]
