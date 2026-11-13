"""Declare the final customer Receipt as a separate document kind.

Choice metadata only: no data conversion, Receipt issuance, or provider sending.
Unrelated user-role and delegation choice changes are deliberately excluded.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0082_completion_attempt_send_lifecycle"),
    ]

    operations = [
        migrations.AlterField(
            model_name="document",
            name="kind",
            field=models.CharField(
                choices=[
                    ("CONTRACT", "Project SOW agreement"),
                    ("INVOICE", "HVAC invoice"),
                    ("RECEIPT", "Final customer Receipt"),
                    ("COMPLETION_FINANCED", "Financed completion certificate"),
                    ("COMPLETION_NON_FINANCED", "Non-financed completion certificate"),
                ],
                max_length=32,
            ),
        ),
    ]
