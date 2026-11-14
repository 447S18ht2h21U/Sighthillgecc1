from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0086_project_sales_status_4995"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectSalesStatusChange",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "previous_status",
                    models.CharField(
                        blank=True,
                        max_length=16,
                        null=True,
                    ),
                ),
                (
                    "new_status",
                    models.CharField(
                        choices=[
                            ("ACTIVE", "Active"),
                            ("WON", "Won"),
                            ("LOST", "Lost"),
                            ("CANCELLED", "Cancelled"),
                            ("INACTIVE", "Inactive"),
                        ],
                        max_length=16,
                    ),
                ),
                ("reason", models.TextField()),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "changed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales_status_changes",
                        to="core.user",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sales_status_history",
                        to="core.project",
                    ),
                ),
            ],
            options={
                "ordering": ["-changed_at", "-pk"],
            },
        ),
    ]
