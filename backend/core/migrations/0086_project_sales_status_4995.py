from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0085_inspection_evidence_retention_4969"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="sales_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("ACTIVE", "Active"),
                    ("WON", "Won"),
                    ("LOST", "Lost"),
                    ("CANCELLED", "Cancelled"),
                    ("INACTIVE", "Inactive"),
                ],
                max_length=16,
                null=True,
                default=None,
            ),
        ),
    ]
