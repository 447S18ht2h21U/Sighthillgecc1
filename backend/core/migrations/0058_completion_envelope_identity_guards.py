"""Completion envelope identity and lifecycle safeguards."""

from django.db import migrations


def install_sqlite_identity_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return
    schema_editor.execute("""
        CREATE TRIGGER gecc_completion_attempt_identity_guard
        BEFORE UPDATE ON core_completionenvelopeattempt
        WHEN NEW.id IS NOT OLD.id
          OR NEW.release_package_id IS NOT OLD.release_package_id
          OR NEW.initiated_by_id IS NOT OLD.initiated_by_id
          OR NEW.provider_account_id IS NOT OLD.provider_account_id
          OR NEW.provider_envelope_id IS NOT OLD.provider_envelope_id
          OR NEW.created_at IS NOT OLD.created_at
          OR (OLD.first_send_started_at IS NOT NULL
              AND NEW.first_send_started_at IS NOT OLD.first_send_started_at)
        BEGIN
            SELECT RAISE(ABORT, 'Completion envelope attempt identity is immutable');
        END
    """)


def remove_sqlite_identity_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER IF EXISTS gecc_completion_attempt_identity_guard")

def install_sqlite_lifecycle_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return
    schema_editor.execute("""
        CREATE TRIGGER gecc_completion_attempt_lifecycle_guard
        BEFORE UPDATE ON core_completionenvelopeattempt
        WHEN NEW.state IS NOT OLD.state
          OR NEW.first_send_started_at IS NOT OLD.first_send_started_at
          OR (NEW.state IS NOT 'AUTH_PENDING' AND NEW.state IS NOT 'CANCELLED_UNSENT')
        BEGIN
            SELECT CASE WHEN NOT (
                OLD.state IS 'AUTH_PENDING'
                AND NEW.state IS 'CANCELLED_UNSENT'
                AND OLD.first_send_started_at IS NULL
                AND NEW.first_send_started_at IS NULL
                AND NEW.provider_envelope_id IS ''
            ) THEN RAISE(ABORT, 'Completion envelope transition is not authorized') END;
        END
    """)


def remove_sqlite_lifecycle_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER IF EXISTS gecc_completion_attempt_lifecycle_guard")

def install_sqlite_initial_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return
    schema_editor.execute("""
        CREATE TRIGGER gecc_completion_attempt_initial_guard
        BEFORE INSERT ON core_completionenvelopeattempt
        WHEN NEW.state IS NOT 'AUTH_PENDING'
          OR NEW.provider_envelope_id IS NOT ''
          OR NEW.first_send_started_at IS NOT NULL
          OR NEW.provider_account_id IS NULL
          OR TRIM(NEW.provider_account_id) = ''
        BEGIN
            SELECT RAISE(ABORT, 'Invalid initial completion envelope state');
        END
    """)


def remove_sqlite_initial_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER IF EXISTS gecc_completion_attempt_initial_guard")

def install_postgresql_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE FUNCTION gecc_completion_attempt_identity_check()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.id IS DISTINCT FROM OLD.id
               OR NEW.release_package_id IS DISTINCT FROM OLD.release_package_id
               OR NEW.initiated_by_id IS DISTINCT FROM OLD.initiated_by_id
               OR NEW.provider_account_id IS DISTINCT FROM OLD.provider_account_id
               OR NEW.provider_envelope_id IS DISTINCT FROM OLD.provider_envelope_id
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR (OLD.first_send_started_at IS NOT NULL
                   AND NEW.first_send_started_at IS DISTINCT FROM OLD.first_send_started_at)
            THEN
                RAISE EXCEPTION 'Completion envelope attempt identity is immutable';
            END IF;
            RETURN NEW;
        END $$;
    """)


def install_postgresql_identity_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE TRIGGER gecc_completion_attempt_identity_update
        BEFORE UPDATE ON core_completionenvelopeattempt
        FOR EACH ROW
        EXECUTE FUNCTION gecc_completion_attempt_identity_check()
    """)

def install_postgresql_lifecycle_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE FUNCTION gecc_completion_attempt_lifecycle_check()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.state IS DISTINCT FROM OLD.state
               OR NEW.first_send_started_at IS DISTINCT FROM OLD.first_send_started_at
               OR NEW.state IS NULL
               OR NEW.state NOT IN ('AUTH_PENDING', 'CANCELLED_UNSENT')
            THEN
                IF NOT (
                    OLD.state IS NOT DISTINCT FROM 'AUTH_PENDING'
                    AND NEW.state IS NOT DISTINCT FROM 'CANCELLED_UNSENT'
                    AND OLD.first_send_started_at IS NULL
                    AND NEW.first_send_started_at IS NULL
                    AND NEW.provider_envelope_id IS NOT DISTINCT FROM ''
                ) THEN
                    RAISE EXCEPTION 'Completion envelope transition is not authorized';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
    """)

def install_postgresql_lifecycle_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE TRIGGER gecc_completion_attempt_lifecycle_update
        BEFORE UPDATE ON core_completionenvelopeattempt
        FOR EACH ROW
        EXECUTE FUNCTION gecc_completion_attempt_lifecycle_check()
    """)

def install_postgresql_initial_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE FUNCTION gecc_completion_attempt_initial_check()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.state IS DISTINCT FROM 'AUTH_PENDING'
               OR NEW.provider_envelope_id IS DISTINCT FROM ''
               OR NEW.first_send_started_at IS NOT NULL
               OR NEW.provider_account_id IS NULL
               OR BTRIM(NEW.provider_account_id) = ''
            THEN
                RAISE EXCEPTION 'Invalid initial completion envelope state';
            END IF;
            RETURN NEW;
        END $$;
    """)

def install_postgresql_initial_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE TRIGGER gecc_completion_attempt_initial_insert
        BEFORE INSERT ON core_completionenvelopeattempt
        FOR EACH ROW
        EXECUTE FUNCTION gecc_completion_attempt_initial_check()
    """)

def remove_postgresql_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        DROP TRIGGER IF EXISTS gecc_completion_attempt_initial_insert ON core_completionenvelopeattempt;
        DROP TRIGGER IF EXISTS gecc_completion_attempt_lifecycle_update ON core_completionenvelopeattempt;
        DROP TRIGGER IF EXISTS gecc_completion_attempt_identity_update ON core_completionenvelopeattempt;
        DROP FUNCTION IF EXISTS gecc_completion_attempt_initial_check();
        DROP FUNCTION IF EXISTS gecc_completion_attempt_lifecycle_check();
        DROP FUNCTION IF EXISTS gecc_completion_attempt_identity_check();
    """)

class Migration(migrations.Migration):
    dependencies = [
        ("core", "0057_completion_envelope_attempt"),
    ]
    operations = [
        migrations.RunPython(install_sqlite_identity_guard, remove_sqlite_identity_guard),
        migrations.RunPython(install_sqlite_lifecycle_guard, remove_sqlite_lifecycle_guard),
        migrations.RunPython(install_sqlite_initial_guard, remove_sqlite_initial_guard),
        migrations.RunPython(install_postgresql_guards, remove_postgresql_guards),
        migrations.RunPython(install_postgresql_lifecycle_guard, migrations.RunPython.noop),
        migrations.RunPython(install_postgresql_initial_guard, migrations.RunPython.noop),
        migrations.RunPython(install_postgresql_identity_trigger, migrations.RunPython.noop),
        migrations.RunPython(install_postgresql_lifecycle_trigger, migrations.RunPython.noop),
        migrations.RunPython(install_postgresql_initial_trigger, migrations.RunPython.noop),
    ]
