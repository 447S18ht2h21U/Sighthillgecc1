from django.db import migrations


TABLE = "core_projectsalesstatuschange"
MESSAGE = "Sales status history is immutable"


def create_guards(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor

    if vendor == "sqlite":
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TRIGGER core_sales_audit_no_update_5003 "
                "BEFORE UPDATE ON core_projectsalesstatuschange "
                "BEGIN SELECT RAISE(ABORT, "
                "'Sales status history is immutable'); END"
            )
            cursor.execute(
                "CREATE TRIGGER core_sales_audit_no_delete_5003 "
                "BEFORE DELETE ON core_projectsalesstatuschange "
                "BEGIN SELECT RAISE(ABORT, "
                "'Sales status history is immutable'); END"
            )
    elif vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE FUNCTION core_sales_audit_reject_5003() "
                "RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION "
                "'Sales status history is immutable'; "
                "END; $$"
            )
            cursor.execute(
                "CREATE TRIGGER core_sales_audit_immutable_5003 "
                "BEFORE UPDATE OR DELETE "
                "ON core_projectsalesstatuschange "
                "FOR EACH ROW "
                "EXECUTE FUNCTION core_sales_audit_reject_5003()"
            )
    else:
        raise RuntimeError(
            "Unsupported database engine for sales audit safeguards"
        )


def drop_guards(apps, schema_editor):
    connection = schema_editor.connection

    if connection.vendor == "sqlite":
        with connection.cursor() as cursor:
            cursor.execute(
                "DROP TRIGGER core_sales_audit_no_update_5003"
            )
            cursor.execute(
                "DROP TRIGGER core_sales_audit_no_delete_5003"
            )
    elif connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "DROP TRIGGER core_sales_audit_immutable_5003 "
                "ON core_projectsalesstatuschange"
            )
            cursor.execute(
                "DROP FUNCTION core_sales_audit_reject_5003()"
            )
    else:
        raise RuntimeError("Unsupported database engine")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0087_project_sales_status_history_5000"),
    ]

    operations = [
        migrations.RunPython(create_guards, drop_guards),
    ]
