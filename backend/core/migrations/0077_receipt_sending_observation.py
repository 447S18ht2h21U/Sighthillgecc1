from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("core", '0076_equipment_catalog_integrity')]

    operations = [
        migrations.CreateModel(
            name="ReceiptSendingObservation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("recipient_email", models.EmailField(max_length=254)),
                ("provider_reference", models.CharField(max_length=256)),
                ("sent_at", models.DateTimeField()),
                ("pdf_sha256", models.CharField(max_length=64)),
                ("observation_source", models.CharField(max_length=40)),
                ("status", models.CharField(default="UNVERIFIED", max_length=20)),
                ("msr", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="receipt_sending_observations", to="core.msr")),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="receipt_sending_observations", to="core.document")),
                ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="receipt_sending_observations_recorded", to="core.user")),
            ],
        ),
    ]
