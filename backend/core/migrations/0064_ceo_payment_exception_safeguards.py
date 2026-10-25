"""Database integrity safeguards for CEO payment exceptions."""

from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER gecc_ceo_payment_exception_insert_guard
            BEFORE INSERT ON core_ceopaymentexception
            BEGIN
                SELECT CASE WHEN
                    NEW.status != 'REQUESTED'
                    OR NEW.decided_by_id IS NOT NULL
                    OR NEW.decided_at IS NOT NULL
                    OR NEW.decision_reason != ''
                    OR NEW.revoked_by_id IS NOT NULL
                    OR NEW.revoked_at IS NOT NULL
                    OR NEW.revocation_reason != ''
                    OR TRIM(COALESCE(NEW.request_reason, '')) = ''
                    OR NOT EXISTS (
                        SELECT 1
                        FROM core_msr m
                        JOIN core_project p
                          ON p.id = m.project_id
                        WHERE m.id = NEW.msr_id
                          AND p.id = NEW.project_id
                          AND p.current_approved_id = m.id
                          AND p.state != 'CANCELLED'
                          AND m.status = 'APPROVED'
                          AND json_valid(m.snapshot) = 1
                          AND json_extract(
                              m.snapshot,
                              '$.payment_option'
                          ) = '100_PERCENT_COMPLETION'
                    )
                    OR NOT EXISTS (
                        SELECT 1
                        FROM core_user u
                        JOIN core_project p
                          ON p.id = NEW.project_id
                        WHERE u.id = NEW.requested_by_id
                          AND u.is_active = 1
                          AND (
                              u.id = p.sales_associate_id
                              OR u.id = p.reviewer_id
                              OR u.role = 'COMPTROLLER'
                          )
                    )
                THEN RAISE(
                    ABORT,
                    'Invalid CEO payment exception request'
                )
                END;
            END;
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_ceo_payment_exception_update_guard
            BEFORE UPDATE ON core_ceopaymentexception
            BEGIN
                SELECT CASE WHEN
                    NEW.id IS NOT OLD.id
                    OR NEW.created_at IS NOT OLD.created_at
                    OR NEW.project_id IS NOT OLD.project_id
                    OR NEW.msr_id IS NOT OLD.msr_id
                    OR NEW.requested_by_id IS NOT OLD.requested_by_id
                    OR NEW.request_reason IS NOT OLD.request_reason
                THEN RAISE(
                    ABORT,
                    'CEO payment exception request identity is immutable'
                )
                END;

                SELECT CASE WHEN NOT (
                    (OLD.status = 'REQUESTED'
                     AND NEW.status IN ('APPROVED', 'REJECTED'))
                    OR
                    (OLD.status = 'APPROVED'
                     AND NEW.status = 'REVOKED')
                )
                THEN RAISE(
                    ABORT,
                    'Invalid CEO payment exception status transition'
                )
                END;

                SELECT CASE WHEN
                    OLD.status = 'REQUESTED'
                    AND NEW.status IN ('APPROVED', 'REJECTED')
                    AND (
                        NEW.decided_by_id IS NULL
                        OR NEW.decided_by_id = NEW.requested_by_id
                        OR NEW.decided_at IS NULL
                        OR TRIM(COALESCE(NEW.decision_reason, '')) = ''
                        OR NEW.revoked_by_id IS NOT NULL
                        OR NEW.revoked_at IS NOT NULL
                        OR COALESCE(NEW.revocation_reason, '') != ''
                        OR NOT EXISTS (
                            SELECT 1
                            FROM core_user u
                            WHERE u.id = NEW.decided_by_id
                              AND u.role = 'CEO'
                              AND u.is_active = 1
                        )
                        OR NOT EXISTS (
                            SELECT 1
                            FROM core_msr m
                            JOIN core_project p
                              ON p.id = m.project_id
                            WHERE m.id = NEW.msr_id
                              AND p.id = NEW.project_id
                              AND p.current_approved_id = m.id
                              AND p.state != 'CANCELLED'
                              AND m.status = 'APPROVED'
                              AND m.snapshot IS NOT NULL
                              AND json_valid(m.snapshot) = 1
                              AND json_extract(
                                  m.snapshot,
                                  '$.payment_option'
                              ) = '100_PERCENT_COMPLETION'
                        )
                    )
                THEN RAISE(
                    ABORT,
                    'Independent active CEO decision required'
                )
                END;

                SELECT CASE WHEN
                    OLD.status = 'APPROVED'
                    AND (
                        NEW.decided_by_id IS NOT OLD.decided_by_id
                        OR NEW.decided_at IS NOT OLD.decided_at
                        OR NEW.decision_reason IS NOT OLD.decision_reason
                        OR NEW.revoked_by_id IS NULL
                        OR NEW.revoked_by_id = NEW.requested_by_id
                        OR NEW.revoked_at IS NULL
                        OR TRIM(NEW.revocation_reason) = ''
                        OR NOT EXISTS (
                            SELECT 1
                            FROM core_user u
                            WHERE u.id = NEW.revoked_by_id
                              AND u.role = 'CEO'
                              AND u.is_active = 1
                        )
                    )
                THEN RAISE(
                    ABORT,
                    'Valid CEO revocation evidence required'
                )
                END;
            END;
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_ceo_payment_exception_delete_guard
            BEFORE DELETE ON core_ceopaymentexception
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'CEO payment exception records cannot be deleted'
                );
            END;
        """)

    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION gecc_ceo_payment_exception_guard()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION
                        'CEO payment exception records cannot be deleted';
                END IF;

                IF TG_OP = 'INSERT' THEN
                    IF NEW.status IS DISTINCT FROM 'REQUESTED'
                       OR NEW.decided_by_id IS NOT NULL
                       OR NEW.decided_at IS NOT NULL
                       OR COALESCE(NEW.decision_reason, '') <> ''
                       OR NEW.revoked_by_id IS NOT NULL
                       OR NEW.revoked_at IS NOT NULL
                       OR COALESCE(NEW.revocation_reason, '') <> ''
                       OR BTRIM(COALESCE(NEW.request_reason, '')) = ''
                       OR NOT EXISTS (
                           SELECT 1
                           FROM core_msr m
                           JOIN core_project p ON p.id = m.project_id
                           WHERE m.id = NEW.msr_id
                             AND p.id = NEW.project_id
                             AND p.current_approved_id = m.id
                             AND p.state <> 'CANCELLED'
                             AND m.status = 'APPROVED'
                             AND m.snapshot->>'payment_option' =
                                 '100_PERCENT_COMPLETION'
                       )
                       OR NOT EXISTS (
                           SELECT 1
                           FROM core_user u
                           JOIN core_project p ON p.id = NEW.project_id
                           WHERE u.id = NEW.requested_by_id
                             AND u.is_active = TRUE
                             AND (
                                 u.id = p.sales_associate_id
                                 OR u.id = p.reviewer_id
                                 OR u.role = 'COMPTROLLER'
                             )
                       )
                    THEN
                        RAISE EXCEPTION 'Invalid CEO payment exception request';
                    END IF;
                    RETURN NEW;
                END IF;

                IF TG_OP = 'UPDATE' THEN
                    IF NEW.id IS DISTINCT FROM OLD.id
                       OR NEW.created_at IS DISTINCT FROM OLD.created_at
                       OR NEW.project_id IS DISTINCT FROM OLD.project_id
                       OR NEW.msr_id IS DISTINCT FROM OLD.msr_id
                       OR NEW.requested_by_id IS DISTINCT FROM OLD.requested_by_id
                       OR NEW.request_reason IS DISTINCT FROM OLD.request_reason
                    THEN
                        RAISE EXCEPTION
                            'CEO payment exception request identity is immutable';
                    END IF;

                    IF NOT (
                        (OLD.status = 'REQUESTED'
                         AND NEW.status IN ('APPROVED', 'REJECTED'))
                        OR
                        (OLD.status = 'APPROVED'
                         AND NEW.status = 'REVOKED')
                    ) THEN
                        RAISE EXCEPTION
                            'Invalid CEO payment exception status transition';
                    END IF;

                    IF OLD.status = 'REQUESTED' THEN
                        IF NEW.decided_by_id IS NULL
                           OR NEW.decided_by_id = NEW.requested_by_id
                           OR NEW.decided_at IS NULL
                           OR BTRIM(COALESCE(NEW.decision_reason, '')) = ''
                           OR NEW.revoked_by_id IS NOT NULL
                           OR NEW.revoked_at IS NOT NULL
                           OR COALESCE(NEW.revocation_reason, '') <> ''
                           OR NOT EXISTS (
                               SELECT 1 FROM core_user u
                               WHERE u.id = NEW.decided_by_id
                                 AND u.role = 'CEO'
                                 AND u.is_active = TRUE
                           )
                           OR NOT EXISTS (
                               SELECT 1
                               FROM core_msr m
                               JOIN core_project p ON p.id = m.project_id
                               WHERE m.id = NEW.msr_id
                                 AND p.id = NEW.project_id
                                 AND p.current_approved_id = m.id
                                 AND p.state <> 'CANCELLED'
                                 AND m.status = 'APPROVED'
                                 AND m.snapshot->>'payment_option' =
                                     '100_PERCENT_COMPLETION'
                           )
                        THEN
                            RAISE EXCEPTION
                                'Independent active CEO decision required';
                        END IF;
                    END IF;

                    IF OLD.status = 'APPROVED' THEN
                        IF NEW.decided_by_id IS DISTINCT FROM OLD.decided_by_id
                           OR NEW.decided_at IS DISTINCT FROM OLD.decided_at
                           OR NEW.decision_reason IS DISTINCT FROM OLD.decision_reason
                           OR NEW.revoked_by_id IS NULL
                           OR NEW.revoked_by_id = NEW.requested_by_id
                           OR NEW.revoked_at IS NULL
                           OR BTRIM(COALESCE(NEW.revocation_reason, '')) = ''
                           OR NOT EXISTS (
                               SELECT 1 FROM core_user u
                               WHERE u.id = NEW.revoked_by_id
                                 AND u.role = 'CEO'
                                 AND u.is_active = TRUE
                           )
                        THEN
                            RAISE EXCEPTION
                                'Valid CEO revocation evidence required';
                        END IF;
                    END IF;

                    RETURN NEW;
                END IF;

                RAISE EXCEPTION 'Unsupported payment exception operation';
            END $$;
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_ceo_payment_exception_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON core_ceopaymentexception
            FOR EACH ROW
            EXECUTE FUNCTION gecc_ceo_payment_exception_guard();
        """)

    else:
        raise RuntimeError(
            "SAFETY STOP: Unsupported database engine."
        )


def uninstall(apps, schema_editor):
    raise RuntimeError(
        "SAFETY STOP: CEO payment exception safeguards require controlled removal."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0063_ceopaymentexception"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]