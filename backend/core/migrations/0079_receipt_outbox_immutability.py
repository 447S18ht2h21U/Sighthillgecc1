"""Database-level immutable Receipt dispatch intent.

Applies to isolated SQLite tests and, after separate authorization,
PostgreSQL deployments. This migration is not an email-sending feature.
"""
from django.db import migrations


SQLITE_UPDATE = """
CREATE TRIGGER receipt_outbox_immutable_update
BEFORE UPDATE ON core_receiptdispatchoutbox
BEGIN
    SELECT RAISE(ABORT, 'Receipt outbox intent is immutable');
END;
"""
SQLITE_DELETE = """
CREATE TRIGGER receipt_outbox_immutable_delete
BEFORE DELETE ON core_receiptdispatchoutbox
BEGIN
    SELECT RAISE(ABORT, 'Receipt outbox intent is immutable');
END;
"""
POSTGRES_FUNCTION = """
CREATE FUNCTION receipt_outbox_deny_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Receipt outbox intent is immutable';
END;
$$;
"""


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "sqlite":
        schema_editor.execute(SQLITE_UPDATE)
        schema_editor.execute(SQLITE_DELETE)
    elif vendor == "postgresql":
        schema_editor.execute(POSTGRES_FUNCTION)
        schema_editor.execute("""
            CREATE TRIGGER receipt_outbox_immutable_update
            BEFORE UPDATE ON core_receiptdispatchoutbox
            FOR EACH ROW EXECUTE FUNCTION receipt_outbox_deny_mutation()
        """)
        schema_editor.execute("""
            CREATE TRIGGER receipt_outbox_immutable_delete
            BEFORE DELETE ON core_receiptdispatchoutbox
            FOR EACH ROW EXECUTE FUNCTION receipt_outbox_deny_mutation()
        """)
    else:
        raise RuntimeError("Unsupported outbox safeguard database vendor")


def uninstall(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor in ("sqlite", "postgresql"):
        schema_editor.execute(
            "DROP TRIGGER receipt_outbox_immutable_update "
            "ON core_receiptdispatchoutbox"
            if vendor == "postgresql"
            else "DROP TRIGGER receipt_outbox_immutable_update"
        )
        schema_editor.execute(
            "DROP TRIGGER receipt_outbox_immutable_delete "
            "ON core_receiptdispatchoutbox"
            if vendor == "postgresql"
            else "DROP TRIGGER receipt_outbox_immutable_delete"
        )
        if vendor == "postgresql":
            schema_editor.execute(
                "DROP FUNCTION receipt_outbox_deny_mutation()"
            )
    else:
        raise RuntimeError("Unsupported outbox safeguard database vendor")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0078_receipt_dispatch_outbox"),
    ]

    operations = [
        migrations.RunPython(install, uninstall),
    ]