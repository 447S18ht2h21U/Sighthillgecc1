from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def restore_guards(apps, schema_editor):
    # SQLite rebuilds this table for AlterField, dropping its original triggers.
    # No historical payload, digest, sequence or actor is rewritten.
    if schema_editor.connection.vendor == 'sqlite':
        for action in ['UPDATE', 'DELETE']:
            schema_editor.execute(f"CREATE TRIGGER IF NOT EXISTS gecc_audit_{action.lower()} BEFORE {action} ON core_auditevent BEGIN SELECT RAISE(ABORT, 'Audit events are append-only'); END")


class Migration(migrations.Migration):
    dependencies = [('core', '0009_signingtestattempt_signingtestobservation_and_more')]
    operations = [
        migrations.AlterField('auditevent', 'actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        # Forward-only: anonymous evidence must not be removed to roll back.
        migrations.RunPython(restore_guards),
    ]
