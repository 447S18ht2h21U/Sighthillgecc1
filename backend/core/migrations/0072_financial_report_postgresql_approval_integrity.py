"""Strengthen financial report approval integrity on isolated PostgreSQL.

This migration is test-installation-only until separately authorized.
Historical migration 0032 is preserved. SQLite triggers are unchanged.
"""

import os

from django.db import migrations


TEST_AUTHORIZATION = "ISOLATED_POSTGRESQL_FINANCIAL_0072"
TEST_DATABASE = "veridian_financial_safeguard_test_0072"
TEST_ROLE = "veridian_test"


def install(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor
    database_name = str(connection.settings_dict.get("NAME", ""))

    if vendor == "sqlite":
        if (
            os.environ.get("VERIDIAN_0072_TEST_INSTALL")
            != "ISOLATED_SQLITE_MEMORY"
            or database_name not in (
                ":memory:",
                "file:memorydb_default?mode=memory&cache=shared",
            )
        ):
            raise RuntimeError(
                "SAFETY STOP: SQLite 0072 installation requires "
                "an explicitly authorized in-memory test database."
            )
        return

    if vendor != "postgresql":
        raise RuntimeError(
            "SAFETY STOP: Unsupported database engine for migration 0072."
        )

    if (
        os.environ.get("VERIDIAN_0072_TEST_INSTALL")
        != TEST_AUTHORIZATION
        or database_name != TEST_DATABASE
    ):
        raise RuntimeError(
            "SAFETY STOP: PostgreSQL 0072 installation is restricted "
            "to the dedicated financial integrity test database."
        )

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user")
        actual_database, actual_user = cursor.fetchone()

    if actual_database != TEST_DATABASE or actual_user != TEST_ROLE:
        raise RuntimeError(
            "SAFETY STOP: PostgreSQL 0072 database identity mismatch."
        )

    schema_editor.execute("""
        CREATE OR REPLACE FUNCTION gecc_financial_report_guard()
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
                IF NEW.status IS DISTINCT FROM 'DRAFT'
                   OR NEW.approved_by_id IS NOT NULL
                   OR NEW.approved_at IS NOT NULL THEN
                    RAISE EXCEPTION
                        'New financial reports must be draft';
                END IF;
                RETURN NEW;
            END IF;

            IF NEW.status IS NULL
               OR NEW.status NOT IN ('DRAFT', 'APPROVED') THEN
                RAISE EXCEPTION
                    'Invalid financial report status';
            END IF;

            IF OLD.status = 'APPROVED' THEN
                RAISE EXCEPTION
                    'Approved financial reports are immutable';
            END IF;

            IF NEW.status = 'DRAFT'
               AND (
                   NEW.approved_by_id IS NOT NULL
                   OR NEW.approved_at IS NOT NULL
               ) THEN
                RAISE EXCEPTION
                    'Draft financial reports cannot have approval evidence';
            END IF;

            IF NEW.status = 'APPROVED' THEN
                IF OLD.status IS DISTINCT FROM 'DRAFT'
                   OR NEW.approved_by_id IS NULL
                   OR NEW.approved_at IS NULL
                   OR NEW.kind IS DISTINCT FROM OLD.kind
                   OR NEW.period_start IS DISTINCT FROM OLD.period_start
                   OR NEW.period_end IS DISTINCT FROM OLD.period_end
                   OR NEW.report_snapshot IS DISTINCT FROM OLD.report_snapshot
                   OR NEW.created_by_id IS DISTINCT FROM OLD.created_by_id
                   OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                    RAISE EXCEPTION
                        'Invalid financial report approval';
                END IF;
            END IF;

            RETURN NEW;
        END $$;
    """)


def uninstall(apps, schema_editor):
    raise RuntimeError(
        "SAFETY STOP: Financial report integrity rollback requires "
        "a separately reviewed migration."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0071_contractor_payment_evidence_safeguards"),
    ]

    operations = [
        migrations.RunPython(install, reverse_code=uninstall),
    ]
