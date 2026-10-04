from django.db import migrations

def install(apps, schema_editor):
    apps.get_model('core', 'AuditHead').objects.get_or_create(pk=1)
    apps.get_model('core', 'LocalCounter').objects.get_or_create(pk=1)
    vendor = schema_editor.connection.vendor
    if vendor == 'postgresql':
        schema_editor.execute('CREATE SEQUENCE gecc_project_number START WITH 101')
        schema_editor.execute("""
        CREATE FUNCTION gecc_msr_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'MSR deletion is prohibited'; END IF;
            IF OLD.status = 'APPROVED' THEN RAISE EXCEPTION 'Approved MSR is immutable'; END IF;
            IF OLD.status = 'SUBMITTED' AND OLD.snapshot::jsonb IS DISTINCT FROM NEW.snapshot::jsonb THEN
                RAISE EXCEPTION 'Submitted MSR commercial fields are frozen';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER gecc_msr_guard BEFORE UPDATE OR DELETE ON core_msr
        FOR EACH ROW EXECUTE FUNCTION gecc_msr_guard();
        CREATE FUNCTION gecc_audit_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Audit events are append-only'; END $$;
        CREATE TRIGGER gecc_audit_guard BEFORE UPDATE OR DELETE ON core_auditevent
        FOR EACH ROW EXECUTE FUNCTION gecc_audit_guard();
        """)
    elif vendor == 'sqlite':
        for sql in [
            "CREATE TRIGGER gecc_msr_immutable BEFORE UPDATE ON core_msr WHEN OLD.status = 'APPROVED' BEGIN SELECT RAISE(ABORT, 'Approved MSR is immutable'); END",
            "CREATE TRIGGER gecc_msr_submitted BEFORE UPDATE ON core_msr WHEN OLD.status = 'SUBMITTED' AND OLD.snapshot != NEW.snapshot BEGIN SELECT RAISE(ABORT, 'Submitted MSR is frozen'); END",
            "CREATE TRIGGER gecc_msr_delete BEFORE DELETE ON core_msr BEGIN SELECT RAISE(ABORT, 'MSR deletion is prohibited'); END",
            "CREATE TRIGGER gecc_audit_update BEFORE UPDATE ON core_auditevent BEGIN SELECT RAISE(ABORT, 'Audit events are append-only'); END",
            "CREATE TRIGGER gecc_audit_delete BEFORE DELETE ON core_auditevent BEGIN SELECT RAISE(ABORT, 'Audit events are append-only'); END",
        ]:
            schema_editor.execute(sql)

def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('DROP TRIGGER gecc_msr_guard ON core_msr; DROP TRIGGER gecc_audit_guard ON core_auditevent; DROP FUNCTION gecc_msr_guard(); DROP FUNCTION gecc_audit_guard(); DROP SEQUENCE gecc_project_number;')
    else:
        for name in ['gecc_msr_immutable', 'gecc_msr_submitted', 'gecc_msr_delete', 'gecc_audit_update', 'gecc_audit_delete']:
            schema_editor.execute(f'DROP TRIGGER {name}')

class Migration(migrations.Migration):
    dependencies = [('core', '0001_initial')]
    operations = [migrations.RunPython(install, uninstall)]
