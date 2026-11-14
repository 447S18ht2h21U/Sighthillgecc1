from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0084_receipt_draft_package"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InstallationInspectionEvidence4969",
            fields=[
                ("id", models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False
                )),
                ("purported_envelope_id", models.CharField(max_length=128)),
                ("bundle_digest", models.CharField(max_length=64)),
                ("source_digest", models.CharField(max_length=64)),
                ("source_data", models.JSONField()),
                ("signed_pdf", models.BinaryField()),
                ("signed_pdf_sha256", models.CharField(max_length=64)),
                ("certificate_pdf", models.BinaryField()),
                ("certificate_sha256", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to=settings.AUTH_USER_MODEL
                )),
                ("msr", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="inspection_evidence_4969",
                    to="core.msr"
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name="installationinspectionevidence4969",
            constraint=models.UniqueConstraint(
                fields=("msr", "purported_envelope_id"),
                name="inspection_envelope_unique_4969"
            ),
        ),
    ]
