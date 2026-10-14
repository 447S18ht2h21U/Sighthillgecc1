import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type = %s AND name = %s",
        ["trigger", "gecc_temporary_project_access_insert_guard"],
    )
    row = cursor.fetchone()

assert row is not None, "Project-access insert trigger is missing."
assert "NEW.status != 'REQUESTED'" in row[0], "Initial-status protection is missing."

print("Step 1907P-90B PASSED: installed trigger explicitly rejects non-REQUESTED initial status.")
