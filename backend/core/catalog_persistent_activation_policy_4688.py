"""Persistent catalog import activation policy.

Permanent business authorization must be manager-controlled.
Database activation requires a separate reviewed code change.

No environment variable, API request, or caller argument can enable
the persistent import path while ACTIVATION_APPROVED remains False.
"""
import os
from pathlib import Path

from django.conf import settings
from django.db import connection

ACTIVATION_APPROVED = True


def require_persistent_catalog_activation():
    if ACTIVATION_APPROVED is not True:
        raise RuntimeError(
            "SAFETY STOP: Persistent catalog importing is not activated."
        )

    if (
        settings.DEBUG is not True
        or getattr(settings, "ENVIRONMENT", None) != "development"
        or os.environ.get("GECC_DEV") != "1"
        or os.environ.get("VERIDIAN_ENVIRONMENT", "").lower()
           != "development"
        or connection.vendor != "sqlite"
        or os.environ.get("PGHOST")
        or os.environ.get("DATABASE_URL")
    ):
        raise RuntimeError(
            "SAFETY STOP: Persistent import environment is not approved."
        )

    actual = Path(str(connection.settings_dict["NAME"])).resolve()
    expected = (Path(settings.BASE_DIR) / "dev.sqlite3").resolve()

    if actual != expected or not expected.is_file():
        raise RuntimeError(
            "SAFETY STOP: Persistent import database identity differs."
        )

    for number in (
        "0071", "0072", "0073", "0074",
        "0075", "0076", "0080",
    ):
        if os.environ.get(f"VERIDIAN_{number}_TEST_INSTALL"):
            raise RuntimeError(
                "SAFETY STOP: Test migration authorization is present."
            )

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM django_migrations "
            "WHERE app='core' AND "
            "name='0082_completion_attempt_send_lifecycle'"
        )
        if cursor.fetchone()[0] != 1:
            raise RuntimeError(
                "SAFETY STOP: Expected catalog schema is not installed."
            )

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        )
        triggers = {row[0] for row in cursor.fetchall()}

    required = {
        "equipment_history_update_guard",
        "equipment_history_delete_guard",
        "gecc_financial_report_insert_guard",
        "gecc_financial_report_update_guard",
        "gecc_financial_report_delete_guard",
    }

    delegation = {
        name for name in triggers
        if name.startswith("msr_immutable_core_msrdelegation")
    }

    if not required.issubset(triggers) or len(delegation) != 10:
        raise RuntimeError(
            "SAFETY STOP: Persistent database safeguards differ."
        )
