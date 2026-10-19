from django.db import migrations


def install(apps, schema_editor):
    table = 'core_customersignatureevidence'
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(f"CREATE TRIGGER gecc_customer_signature_guard BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION gecc_audit_guard()")
    elif schema_editor.connection.vendor == 'sqlite':
        for action in ("UPDATE", "DELETE"):
            schema_editor.execute(f"CREATE TRIGGER gecc_customer_signature_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Customer signature evidence is immutable'); END")
    else:
        raise RuntimeError('Unsupported database backend for signature evidence safeguards')


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("DROP TRIGGER gecc_customer_signature_guard ON core_customersignatureevidence")
    elif schema_editor.connection.vendor == 'sqlite':
        for action in ("update", "delete"):
            schema_editor.execute(f"DROP TRIGGER gecc_customer_signature_{action}")
    else:
        raise RuntimeError('Unsupported database backend for signature evidence safeguards')


class Migration(migrations.Migration):
    dependencies = [("core", "0051_temporary_project_access_approval_authority")]
    operations = [migrations.RunPython(install, uninstall)]
