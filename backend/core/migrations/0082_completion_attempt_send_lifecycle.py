"""Controlled completion-envelope send lifecycle guards.

Permits only audited first-send intent and terminal provider-result
recording. Does not contact DocuSign or authorize live sending.
Existing initial-insert protection remains installed.
"""
import importlib

from django.db import migrations


def forward(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS gecc_completion_attempt_identity_guard"
        )
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS gecc_completion_attempt_lifecycle_guard"
        )

        schema_editor.execute("""
            CREATE TRIGGER gecc_completion_attempt_identity_guard
            BEFORE UPDATE ON core_completionenvelopeattempt
            WHEN NEW.id IS NOT OLD.id
              OR NEW.release_package_id IS NOT OLD.release_package_id
              OR NEW.initiated_by_id IS NOT OLD.initiated_by_id
              OR NEW.provider_account_id IS NOT OLD.provider_account_id
              OR NEW.created_at IS NOT OLD.created_at
              OR (
                  NEW.provider_envelope_id IS NOT OLD.provider_envelope_id
                  AND NOT (
                      OLD.state IS 'NETWORK_STARTED'
                      AND NEW.state IS 'SENT_UNCHECKED'
                      AND OLD.provider_envelope_id IS ''
                      AND length(NEW.provider_envelope_id) = 36
                  )
              )
              OR (
                  OLD.first_send_started_at IS NOT NULL
                  AND NEW.first_send_started_at
                      IS NOT OLD.first_send_started_at
              )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Completion envelope attempt identity is immutable'
                );
            END
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_completion_attempt_lifecycle_guard
            BEFORE UPDATE ON core_completionenvelopeattempt
            WHEN NEW.state IS NOT OLD.state
              OR NEW.first_send_started_at
                  IS NOT OLD.first_send_started_at
              OR NEW.provider_envelope_id IS NOT OLD.provider_envelope_id
            BEGIN
                SELECT CASE WHEN NOT (
                    (
                        OLD.state IS 'AUTH_PENDING'
                        AND NEW.state IS 'CANCELLED_UNSENT'
                        AND OLD.first_send_started_at IS NULL
                        AND NEW.first_send_started_at IS NULL
                        AND NEW.provider_envelope_id IS ''
                    )
                    OR
                    (
                        OLD.state IS 'AUTH_PENDING'
                        AND NEW.state IS 'NETWORK_STARTED'
                        AND OLD.first_send_started_at IS NULL
                        AND NEW.first_send_started_at IS NOT NULL
                        AND NEW.provider_envelope_id IS ''
                        AND EXISTS (
                            SELECT 1
                            FROM core_auditevent a
                            JOIN core_user u ON u.id = a.actor_id
                            JOIN core_releasepackage p
                              ON p.id = NEW.release_package_id
                            JOIN core_signingplan sp ON sp.id = p.plan_id
                            JOIN core_msr msr ON msr.id = sp.msr_id
                            WHERE a.action =
                              'completion_envelope.send_authorization_recorded'
                              AND lower(replace(
                                json_extract(a.payload, '$.attempt_id'),
                                '-', ''
                              )) = lower(NEW.id)
                              AND json_extract(
                                a.payload, '$.provider_account_id'
                              ) = NEW.provider_account_id
                              AND lower(replace(
                                json_extract(
                                  a.payload, '$.release_package_id'
                                ), '-', ''
                              )) = lower(NEW.release_package_id)
                              AND json_extract(
                                a.payload, '$.release_package_digest'
                              ) = p.digest
                              AND lower(replace(
                                json_extract(a.payload, '$.approved_msr_id'),
                                '-', ''
                              )) = lower(msr.id)
                              AND lower(replace(
                                json_extract(a.payload, '$.project_id'),
                                '-', ''
                              )) = lower(msr.project_id)
                              AND lower(replace(
                                json_extract(
                                  a.payload, '$.initiating_comptroller_id'
                                ), '-', ''
                              )) = lower(NEW.initiated_by_id)
                              AND lower(replace(
                                json_extract(
                                  a.payload, '$.authorizing_actor_id'
                                ), '-', ''
                              )) = lower(a.actor_id)
                              AND u.is_active = 1
                              AND u.role IN ('SALES_MANAGER', 'CEO')
                              AND json_extract(
                                a.payload, '$.attempt_state'
                              ) = 'AUTH_PENDING'
                              AND json_extract(
                                a.payload, '$.live_send_authorized'
                              ) = 0
                        )
                    )
                    OR
                    (
                        OLD.state IS 'NETWORK_STARTED'
                        AND NEW.state IS 'SENT_UNCHECKED'
                        AND OLD.first_send_started_at IS NOT NULL
                        AND NEW.first_send_started_at
                            IS OLD.first_send_started_at
                        AND OLD.provider_envelope_id IS ''
                        AND length(NEW.provider_envelope_id) = 36
                        AND substr(NEW.provider_envelope_id, 9, 1) = '-'
                        AND substr(NEW.provider_envelope_id, 14, 1) = '-'
                        AND substr(NEW.provider_envelope_id, 19, 1) = '-'
                        AND substr(NEW.provider_envelope_id, 24, 1) = '-'
                        AND replace(
                            NEW.provider_envelope_id, '-', ''
                        ) NOT GLOB '*[^0-9a-f]*'
                    )
                    OR
                    (
                        OLD.state IS 'NETWORK_STARTED'
                        AND NEW.state IS 'SEND_UNCERTAIN'
                        AND OLD.first_send_started_at IS NOT NULL
                        AND NEW.first_send_started_at
                            IS OLD.first_send_started_at
                        AND NEW.provider_envelope_id IS ''
                    )
                ) THEN RAISE(
                    ABORT,
                    'Completion envelope transition is not authorized'
                ) END;
            END
        """)
        return

    if vendor == "postgresql":
        schema_editor.execute("""
            CREATE OR REPLACE FUNCTION
            gecc_completion_attempt_identity_check()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.id IS DISTINCT FROM OLD.id
                   OR NEW.release_package_id
                      IS DISTINCT FROM OLD.release_package_id
                   OR NEW.initiated_by_id
                      IS DISTINCT FROM OLD.initiated_by_id
                   OR NEW.provider_account_id
                      IS DISTINCT FROM OLD.provider_account_id
                   OR NEW.created_at IS DISTINCT FROM OLD.created_at
                   OR (
                      NEW.provider_envelope_id
                          IS DISTINCT FROM OLD.provider_envelope_id
                      AND NOT (
                          OLD.state = 'NETWORK_STARTED'
                          AND NEW.state = 'SENT_UNCHECKED'
                          AND OLD.provider_envelope_id = ''
                          AND NEW.provider_envelope_id ~
                              '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                      )
                   )
                   OR (
                      OLD.first_send_started_at IS NOT NULL
                      AND NEW.first_send_started_at
                          IS DISTINCT FROM OLD.first_send_started_at
                   )
                THEN
                    RAISE EXCEPTION
                    'Completion envelope attempt identity is immutable';
                END IF;
                RETURN NEW;
            END $$;
        """)

        schema_editor.execute("""
            CREATE OR REPLACE FUNCTION
            gecc_completion_attempt_lifecycle_check()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.state IS DISTINCT FROM OLD.state
                   OR NEW.first_send_started_at
                      IS DISTINCT FROM OLD.first_send_started_at
                   OR NEW.provider_envelope_id
                      IS DISTINCT FROM OLD.provider_envelope_id
                THEN
                    IF NOT (
                      (
                        OLD.state = 'AUTH_PENDING'
                        AND NEW.state = 'CANCELLED_UNSENT'
                        AND OLD.first_send_started_at IS NULL
                        AND NEW.first_send_started_at IS NULL
                        AND NEW.provider_envelope_id = ''
                      )
                      OR
                      (
                        OLD.state = 'AUTH_PENDING'
                        AND NEW.state = 'NETWORK_STARTED'
                        AND OLD.first_send_started_at IS NULL
                        AND NEW.first_send_started_at IS NOT NULL
                        AND NEW.provider_envelope_id = ''
                        AND EXISTS (
                          SELECT 1
                          FROM core_auditevent a
                          JOIN core_user u ON u.id = a.actor_id
                          JOIN core_releasepackage p
                            ON p.id = NEW.release_package_id
                          JOIN core_signingplan sp ON sp.id = p.plan_id
                          JOIN core_msr msr ON msr.id = sp.msr_id
                          WHERE a.action =
                            'completion_envelope.send_authorization_recorded'
                            AND (a.payload ->> 'attempt_id') = NEW.id::text
                            AND (a.payload ->> 'provider_account_id')
                                = NEW.provider_account_id
                            AND (a.payload ->> 'release_package_id')
                                = NEW.release_package_id::text
                            AND (a.payload ->> 'release_package_digest')
                                = p.digest
                            AND (a.payload ->> 'approved_msr_id')
                                = msr.id::text
                            AND (a.payload ->> 'project_id')
                                = msr.project_id::text
                            AND (a.payload ->> 'initiating_comptroller_id')
                                = NEW.initiated_by_id::text
                            AND (a.payload ->> 'authorizing_actor_id')
                                = a.actor_id::text
                            AND u.is_active = TRUE
                            AND u.role IN ('SALES_MANAGER', 'CEO')
                            AND (a.payload ->> 'attempt_state')
                                = 'AUTH_PENDING'
                            AND (a.payload ->> 'live_send_authorized')
                                = 'false'
                        )
                      )
                      OR
                      (
                        OLD.state = 'NETWORK_STARTED'
                        AND NEW.state = 'SENT_UNCHECKED'
                        AND OLD.first_send_started_at IS NOT NULL
                        AND NEW.first_send_started_at
                            IS NOT DISTINCT FROM OLD.first_send_started_at
                        AND OLD.provider_envelope_id = ''
                        AND NEW.provider_envelope_id ~
                            '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                      )
                      OR
                      (
                        OLD.state = 'NETWORK_STARTED'
                        AND NEW.state = 'SEND_UNCERTAIN'
                        AND OLD.first_send_started_at IS NOT NULL
                        AND NEW.first_send_started_at
                            IS NOT DISTINCT FROM OLD.first_send_started_at
                        AND NEW.provider_envelope_id = ''
                      )
                    ) THEN
                        RAISE EXCEPTION
                        'Completion envelope transition is not authorized';
                    END IF;
                END IF;
                RETURN NEW;
            END $$;
        """)
        return

    raise RuntimeError(
        "Unsupported database backend for completion lifecycle."
    )


def reverse(apps, schema_editor):
    old = importlib.import_module(
        "core.migrations.0058_completion_envelope_identity_guards"
    )
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS gecc_completion_attempt_lifecycle_guard"
        )
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS gecc_completion_attempt_identity_guard"
        )
        old.install_sqlite_identity_guard(apps, schema_editor)
        old.install_sqlite_lifecycle_guard(apps, schema_editor)
        return

    if vendor == "postgresql":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS "
            "gecc_completion_attempt_identity_update "
            "ON core_completionenvelopeattempt"
        )
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS "
            "gecc_completion_attempt_lifecycle_update "
            "ON core_completionenvelopeattempt"
        )
        schema_editor.execute(
            "DROP FUNCTION IF EXISTS gecc_completion_attempt_identity_check()"
        )
        schema_editor.execute(
            "DROP FUNCTION IF EXISTS gecc_completion_attempt_lifecycle_check()"
        )
        old.install_postgresql_guards(apps, schema_editor)
        old.install_postgresql_lifecycle_guard(apps, schema_editor)
        old.install_postgresql_identity_trigger(apps, schema_editor)
        old.install_postgresql_lifecycle_trigger(apps, schema_editor)
        return

    raise RuntimeError("Unsupported database backend.")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0081_expedited_signing_records"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
