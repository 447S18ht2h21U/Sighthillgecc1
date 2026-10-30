"""Contractor payment issuance and settlement integrity safeguards.

SAFETY FOUNDATION ONLY.

Do not apply this migration until the complete SQLite and PostgreSQL
database safeguards have been implemented and independently tested.
"""

from django.db import migrations


SQLITE_ISSUANCE_GUARDS = (
    """
    CREATE TRIGGER gecc_contractor_issuance_insert_guard
    BEFORE INSERT ON core_contractorpaymentissuance
    BEGIN
        SELECT CASE WHEN
            NEW.amount <= 0
            OR TRIM(COALESCE(NEW.transaction_reference, '')) = ''
            OR NEW.payment_method NOT IN ('ACH', 'WIRE', 'CHECK', 'OTHER')
            OR NEW.issued_at IS NULL
            OR julianday(NEW.issued_at) IS NULL
            OR NOT EXISTS (
                SELECT 1 FROM core_user u
                WHERE u.id = NEW.issued_by_id
                  AND u.role = 'CEO'
                  AND u.is_active = 1
            )
            OR NOT EXISTS (
                SELECT 1 FROM core_contractorpaymentrecord p
                WHERE p.id = NEW.payment_record_id
                  AND p.status = 'APPROVED'
                  AND p.approved_by_id IS NOT NULL
                  AND p.approved_at IS NOT NULL
                  AND julianday(p.approved_at) IS NOT NULL
                  AND julianday(NEW.issued_at) >= julianday(p.approved_at)
                  AND p.final_amount = NEW.amount
                  AND p.final_amount > 0
            )
        THEN RAISE(
            ABORT,
            'Invalid contractor payment issuance'
        )
        END;
    END;
    """,
    """
    CREATE TRIGGER gecc_contractor_issuance_update_guard
    BEFORE UPDATE ON core_contractorpaymentissuance
    BEGIN
        SELECT RAISE(ABORT, 'Contractor payment issuance is immutable');
    END;
    """,
    """
    CREATE TRIGGER gecc_contractor_issuance_delete_guard
    BEFORE DELETE ON core_contractorpaymentissuance
    BEGIN
        SELECT RAISE(ABORT, 'Contractor payment issuance cannot be deleted');
    END;
    """,
)

SQLITE_SETTLEMENT_GUARDS = (
    """
    CREATE TRIGGER gecc_contractor_settlement_insert_guard
    BEFORE INSERT ON core_contractorpaymentsettlementverification
    BEGIN
        SELECT CASE WHEN
            NEW.cleared_amount <= 0
            OR TRIM(COALESCE(NEW.evidence_reference, '')) = ''
            OR NEW.settlement_date IS NULL
            OR NEW.verified_at IS NULL
            OR NOT EXISTS (
                SELECT 1
                FROM core_user u
                WHERE u.id = NEW.verified_by_id
                  AND u.role = 'COMPTROLLER'
                  AND u.is_active = 1
            )
            OR NOT EXISTS (
                SELECT 1
                FROM core_contractorpaymentissuance i
                JOIN core_contractorpaymentrecord p
                  ON p.id = i.payment_record_id
                WHERE i.id = NEW.issuance_id
                  AND i.payment_record_id = NEW.payment_record_id
                  AND p.status = 'APPROVED'
                  AND p.approved_by_id IS NOT NULL
                  AND p.approved_at IS NOT NULL
                  AND p.final_amount > 0
                  AND i.amount = p.final_amount
                  AND NEW.cleared_amount = i.amount
                  AND NEW.verified_by_id != i.issued_by_id
                  AND DATE(NEW.settlement_date) >= DATE(i.issued_at)
                  AND DATE(NEW.verified_at) >= DATE(NEW.settlement_date)
                  AND julianday(NEW.verified_at) >= julianday(i.issued_at)
            )
        THEN RAISE(
            ABORT,
            'Invalid contractor payment settlement verification'
        )
        END;
    END;
    """,
    """
    CREATE TRIGGER gecc_contractor_settlement_update_guard
    BEFORE UPDATE ON core_contractorpaymentsettlementverification
    BEGIN
        SELECT RAISE(
            ABORT,
            'Contractor settlement verification is immutable'
        );
    END;
    """,
    """
    CREATE TRIGGER gecc_contractor_settlement_delete_guard
    BEFORE DELETE ON core_contractorpaymentsettlementverification
    BEGIN
        SELECT RAISE(
            ABORT,
            'Contractor settlement verification cannot be deleted'
        );
    END;
    """,
)

SQLITE_PAYMENT_TRANSITION_GUARDS = (
    """
    CREATE TRIGGER gecc_contractor_verified_paid_guard
    BEFORE UPDATE ON core_contractorpaymentrecord
    BEGIN
        SELECT CASE WHEN
            OLD.status = 'APPROVED'
            AND (
                NEW.approved_by_id IS NOT OLD.approved_by_id
                OR NEW.approved_at IS NOT OLD.approved_at
                OR NEW.created_by_id IS NOT OLD.created_by_id
                OR NEW.payment_period_start IS NOT OLD.payment_period_start
                OR NEW.payment_period_end IS NOT OLD.payment_period_end
            )
        THEN RAISE(
            ABORT,
            'Approved contractor payment approval identity is immutable'
        )
        END;

        SELECT CASE WHEN
            NEW.status = 'PAID'
            AND OLD.status != 'PAID'
            AND (
                OLD.status != 'APPROVED'
                OR NEW.paid_at IS NULL
                OR NOT EXISTS (
                    SELECT 1
                    FROM core_contractorpaymentissuance i
                    JOIN core_contractorpaymentsettlementverification s
                      ON s.issuance_id = i.id

                    WHERE i.payment_record_id = NEW.id
                      AND s.payment_record_id = NEW.id
                      AND i.issued_by_id != s.verified_by_id
                      AND NEW.final_amount > 0
                      AND i.amount = NEW.final_amount
                      AND s.cleared_amount = NEW.final_amount
                      AND TRIM(COALESCE(i.transaction_reference, '')) != ''
                      AND TRIM(COALESCE(s.evidence_reference, '')) != ''
                      AND s.verified_at IS NOT NULL
                      AND s.settlement_date IS NOT NULL
                      AND DATE(s.settlement_date) >= DATE(i.issued_at)
                      AND DATE(s.verified_at) >= DATE(s.settlement_date)
                      AND julianday(s.verified_at) >= julianday(i.issued_at)
                      AND NEW.paid_at >= s.verified_at
                )
            )
        THEN RAISE(
            ABORT,
            'Contractor payment requires independently verified settlement'
        )
        END;
    END;
    """,
)

POSTGRESQL_ISSUANCE_GUARDS = """
CREATE FUNCTION gecc_contractor_issuance_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION
            'Contractor payment issuance is immutable';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'Contractor payment issuance cannot be deleted';
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.amount IS NULL
           OR NEW.amount <= 0
           OR BTRIM(COALESCE(NEW.transaction_reference, '')) = ''
           OR NEW.payment_method IS NULL
           OR NEW.payment_method NOT IN ('ACH', 'WIRE', 'CHECK', 'OTHER')
           OR NEW.issued_at IS NULL
           OR NOT EXISTS (
               SELECT 1
               FROM core_user u
               WHERE u.id = NEW.issued_by_id
                 AND u.role = 'CEO'
                 AND u.is_active = TRUE
           )
           OR NOT EXISTS (
               SELECT 1
               FROM core_contractorpaymentrecord p
               WHERE p.id = NEW.payment_record_id
                 AND p.status = 'APPROVED'
                 AND p.approved_by_id IS NOT NULL
                 AND p.approved_at IS NOT NULL
                 AND p.final_amount > 0
                 AND p.final_amount = NEW.amount
                 AND NEW.issued_at >= p.approved_at
           )
        THEN
            RAISE EXCEPTION
                'Invalid contractor payment issuance';
        END IF;

        RETURN NEW;
    END IF;

    RAISE EXCEPTION
        'Unsupported contractor payment issuance operation';
END $$;

CREATE TRIGGER gecc_contractor_issuance_guard
BEFORE INSERT OR UPDATE OR DELETE
ON core_contractorpaymentissuance
FOR EACH ROW
EXECUTE FUNCTION gecc_contractor_issuance_guard();
"""

POSTGRESQL_SETTLEMENT_GUARDS = """
CREATE FUNCTION gecc_contractor_settlement_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION
            'Contractor settlement verification is immutable';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'Contractor settlement verification cannot be deleted';
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.cleared_amount IS NULL
           OR NEW.cleared_amount <= 0
           OR BTRIM(COALESCE(NEW.evidence_reference, '')) = ''
           OR NEW.settlement_date IS NULL
           OR NEW.verified_at IS NULL
           OR NOT EXISTS (
               SELECT 1
               FROM core_user u
               WHERE u.id = NEW.verified_by_id
                 AND u.role = 'COMPTROLLER'
                 AND u.is_active = TRUE
           )
           OR NOT EXISTS (
               SELECT 1
               FROM core_contractorpaymentissuance i
               JOIN core_contractorpaymentrecord p
                 ON p.id = i.payment_record_id
               WHERE i.id = NEW.issuance_id
                 AND i.payment_record_id = NEW.payment_record_id
                 AND p.status = 'APPROVED'
                 AND p.approved_by_id IS NOT NULL
                 AND p.approved_at IS NOT NULL
                 AND p.final_amount > 0
                 AND i.amount = p.final_amount
                 AND NEW.cleared_amount = i.amount
                 AND NEW.verified_by_id <> i.issued_by_id
                 AND NEW.settlement_date >= (i.issued_at AT TIME ZONE 'America/New_York')::date
                 AND NEW.verified_at >= i.issued_at
                 AND (NEW.verified_at AT TIME ZONE 'America/New_York')::date >= NEW.settlement_date
           )
        THEN
            RAISE EXCEPTION
                'Invalid contractor payment settlement verification';
        END IF;

        RETURN NEW;
    END IF;

    RAISE EXCEPTION
        'Unsupported contractor settlement operation';
END $$;

CREATE TRIGGER gecc_contractor_settlement_guard
BEFORE INSERT OR UPDATE OR DELETE
ON core_contractorpaymentsettlementverification
FOR EACH ROW
EXECUTE FUNCTION gecc_contractor_settlement_guard();
"""

POSTGRESQL_PAYMENT_TRANSITION_GUARDS = """
CREATE FUNCTION gecc_contractor_verified_paid_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = 'APPROVED'
       AND (
           NEW.approved_by_id IS DISTINCT FROM OLD.approved_by_id
           OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
           OR NEW.created_by_id IS DISTINCT FROM OLD.created_by_id
           OR NEW.payment_period_start IS DISTINCT FROM OLD.payment_period_start
           OR NEW.payment_period_end IS DISTINCT FROM OLD.payment_period_end
       )
    THEN
        RAISE EXCEPTION
            'Approved contractor payment approval identity is immutable';
    END IF;

    IF NEW.status = 'APPROVED'
       AND (
           OLD.status <> 'DRAFT'
           OR NEW.approved_by_id IS NULL
           OR NEW.approved_at IS NULL
       )
    THEN
        RAISE EXCEPTION
            'Invalid contractor payment approval';
    END IF;

    IF NEW.status = 'PAID'
       AND OLD.status IS DISTINCT FROM 'PAID'
    THEN
        IF OLD.status <> 'APPROVED'
           OR NEW.paid_at IS NULL
           OR NOT EXISTS (
               SELECT 1
               FROM core_contractorpaymentissuance i
               JOIN core_contractorpaymentsettlementverification s
                 ON s.issuance_id = i.id
               WHERE i.payment_record_id = NEW.id
                 AND s.payment_record_id = NEW.id
                 AND i.issued_by_id <> s.verified_by_id
                 AND NEW.final_amount > 0
                 AND i.amount = NEW.final_amount
                 AND s.cleared_amount = NEW.final_amount
                 AND BTRIM(COALESCE(i.transaction_reference, '')) <> ''
                 AND BTRIM(COALESCE(s.evidence_reference, '')) <> ''
                 AND s.verified_at IS NOT NULL
                 AND s.settlement_date IS NOT NULL
                 AND s.settlement_date >=
                     (i.issued_at AT TIME ZONE 'America/New_York')::date
                 AND s.verified_at >= i.issued_at
                 AND (s.verified_at AT TIME ZONE 'America/New_York')::date
                     >= s.settlement_date
                 AND NEW.paid_at >= s.verified_at
           )
        THEN
            RAISE EXCEPTION
                'Contractor payment requires independently verified settlement';
        END IF;
    END IF;

    RETURN NEW;
END $$;

CREATE TRIGGER gecc_contractor_verified_paid_guard
BEFORE UPDATE ON core_contractorpaymentrecord
FOR EACH ROW
EXECUTE FUNCTION gecc_contractor_verified_paid_guard();
"""

def install(apps, schema_editor):
    import os

    connection = schema_editor.connection
    vendor = connection.vendor
    database_name = str(connection.settings_dict.get("NAME", ""))

    authorization = os.environ.get(
        "VERIDIAN_0071_TEST_INSTALL", ""
    )

    if vendor == "postgresql":
        if (
            authorization != "ISOLATED_POSTGRESQL_20261026"
            or database_name
            != "veridian_contractor_safeguard_test_20261026"
        ):
            raise RuntimeError(
                "SAFETY STOP: PostgreSQL 0071 installation "
                "is restricted to the isolated test database."
            )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_database(), current_user"
            )
            actual_name, actual_user = cursor.fetchone()

        if (
            actual_name
            != "veridian_contractor_safeguard_test_20261026"
            or actual_user != "veridian_test"
        ):
            raise RuntimeError(
                "SAFETY STOP: PostgreSQL connection identity mismatch."
            )

        statements = (
            POSTGRESQL_ISSUANCE_GUARDS,
            POSTGRESQL_SETTLEMENT_GUARDS,
            POSTGRESQL_PAYMENT_TRANSITION_GUARDS,
        )

    elif vendor == "sqlite":
        if (
            authorization != "ISOLATED_SQLITE_MEMORY"
            or database_name not in (
                ":memory:",
                "file:memorydb_default?mode=memory&cache=shared",
            )
        ):
            raise RuntimeError(
                "SAFETY STOP: SQLite 0071 installation "
                "requires an isolated in-memory database."
            )

        statements = (
            *SQLITE_ISSUANCE_GUARDS,
            *SQLITE_SETTLEMENT_GUARDS,
            *SQLITE_PAYMENT_TRANSITION_GUARDS,
        )

    else:
        raise RuntimeError(
            "SAFETY STOP: Unsupported database engine."
        )

    for statement in statements:
        schema_editor.execute(statement)



def uninstall(apps, schema_editor):
    raise RuntimeError(
        "SAFETY STOP: Removing financial integrity safeguards "
        "requires a separately reviewed rollback migration."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0070_contractorpaymentissuance_and_more"),
    ]

    operations = [
        migrations.RunPython(install, reverse_code=uninstall),
    ]