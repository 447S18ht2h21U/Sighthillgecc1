import uuid
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0077_receipt_sending_observation"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReceiptDispatchOutbox",
            fields=[
                ("id", models.UUIDField(
                    primary_key=True, default=uuid.uuid4,
                    editable=False, serialize=False,
                )),
                ("idempotency_key", models.CharField(max_length=128)),
                ("recipient_email", models.EmailField(max_length=254)),
                ("pdf_sha256", models.CharField(max_length=64)),
                ("status", models.CharField(
                    max_length=16, default="PENDING",
                )),
                ("created_at", models.DateTimeField(
                    default=django.utils.timezone.now,
                    editable=False,
                )),
                ("project", models.ForeignKey(
                    to="core.project",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="receipt_dispatch_outbox_entries",
                )),
                ("msr", models.ForeignKey(
                    to="core.msr",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="receipt_dispatch_outbox_entries",
                )),
                ("document", models.ForeignKey(
                    to="core.document",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="receipt_dispatch_outbox_entries",
                )),
                ("requested_by", models.ForeignKey(
                    to="core.user",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="receipt_dispatch_outbox_requests",
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name="receiptdispatchoutbox",
            constraint=models.UniqueConstraint(
                fields=("project", "idempotency_key"),
                name="receipt_outbox_unique_project_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="receiptdispatchoutbox",
            constraint=models.CheckConstraint(
                condition=models.Q(status="PENDING"),
                name="receipt_outbox_pending_only",
            ),
        ),
    ]