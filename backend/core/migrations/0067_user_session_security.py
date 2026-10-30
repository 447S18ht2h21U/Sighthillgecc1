"""Introduce a private, per-account session security token.

Existing accounts receive independently generated tokens.
The field is made non-null only after the backfill completes.
"""

import uuid

from django.db import migrations, models


def populate_session_tokens(apps, schema_editor):
    User = apps.get_model("core", "User")
    database = schema_editor.connection.alias

    for user_id in (
        User.objects.using(database)
        .order_by("pk")
        .values_list("pk", flat=True)
        .iterator()
    ):
        User.objects.using(database).filter(
            pk=user_id
        ).update(session_security_token=uuid.uuid4())


def enforce_token_integrity(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER gecc_user_session_token_insert_guard
            BEFORE INSERT ON core_user
            WHEN NEW.session_security_token IS NULL
                 OR LENGTH(NEW.session_security_token) != 32
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'User session security token is required'
                );
            END;
        """)

        schema_editor.execute("""
            CREATE TRIGGER gecc_user_session_token_update_guard
            BEFORE UPDATE ON core_user
            WHEN NEW.session_security_token IS NULL
                 OR LENGTH(NEW.session_security_token) != 32
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'User session security token is required'
                );
            END;
        """)

    elif vendor == "postgresql":
        schema_editor.execute("""
            ALTER TABLE core_user
            ALTER COLUMN session_security_token SET NOT NULL;
        """)

    else:
        raise RuntimeError(
            "SAFETY STOP: Unsupported database engine."
        )


def block_integrity_removal(apps, schema_editor):
    raise RuntimeError(
        "SAFETY STOP: Session security safeguards require controlled removal."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0066_customer_payment_bank_confirmation_safeguards"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="session_security_token",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(
            populate_session_tokens,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    enforce_token_integrity,
                    reverse_code=block_integrity_removal,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="user",
                    name="session_security_token",
                    field=models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                    ),
                ),
            ],
        ),
    ]
