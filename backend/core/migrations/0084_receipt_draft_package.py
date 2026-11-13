"""Immutable draft Receipt package; no customer issuance authority."""

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def install_immutability(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER receipt_draft_immutable_update
            BEFORE UPDATE ON core_receiptdraftpackage
            BEGIN
                SELECT RAISE(ABORT, 'Immutable draft package');
            END;
        """)
        schema_editor.execute("""
            CREATE TRIGGER receipt_draft_immutable_delete
            BEFORE DELETE ON core_receiptdraftpackage
            BEGIN
                SELECT RAISE(ABORT, 'Immutable draft package');
            END;
        """)
    elif vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION core_receipt_draft_immutable()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'Immutable draft package';
            END;
            $$;
        """)
        schema_editor.execute("""
            CREATE TRIGGER receipt_draft_immutable
            BEFORE UPDATE OR DELETE ON core_receiptdraftpackage
            FOR EACH ROW
            EXECUTE FUNCTION core_receipt_draft_immutable();
        """)
    else:
        raise RuntimeError(
            "No immutable package trigger for this database backend."
        )


def remove_immutability(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "sqlite":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS receipt_draft_immutable_update"
        )
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS receipt_draft_immutable_delete"
        )
    elif vendor == "postgresql":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS receipt_draft_immutable "
            "ON core_receiptdraftpackage"
        )
        schema_editor.execute(
            "DROP FUNCTION IF EXISTS core_receipt_draft_immutable()"
        )
    else:
        raise RuntimeError("Unsupported database backend.")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0083_final_customer_receipt_kind"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReceiptDraftPackage",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False,
                )),
                ("snapshot_sha256", models.CharField(max_length=64)),
                ("approved_reference_sha256", models.CharField(max_length=64)),
                ("receipt_sha256", models.CharField(max_length=64)),
                ("addendum_sha256", models.CharField(max_length=64)),
                ("archive_sha256", models.CharField(max_length=64)),
                ("equipment_count", models.PositiveIntegerField()),
                ("content", models.BinaryField()),
                ("status", models.CharField(
                    default="DRAFT_NOT_ISSUED", max_length=24,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="retained_receipt_draft_packages",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("msr", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="retained_receipt_draft_packages",
                    to="core.msr",
                )),
                ("project", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="retained_receipt_draft_packages",
                    to="core.project",
                )),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("msr", "archive_sha256"),
                        name="receipt_draft_package_unique_bytes",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(status="DRAFT_NOT_ISSUED"),
                        name="receipt_draft_package_status_draft",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            install_immutability, remove_immutability
        ),
    ]
