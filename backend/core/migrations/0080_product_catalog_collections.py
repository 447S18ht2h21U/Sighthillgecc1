"""Protected in-memory foundation for independently named product catalogs."""
import os

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import uuid


def verify_isolated_catalog_install(apps, schema_editor):
    connection = schema_editor.connection
    name = str(connection.settings_dict.get("NAME", ""))

    if (
        connection.vendor != "sqlite"
        or name not in (
            ":memory:",
            "file:memorydb_default?mode=memory&cache=shared",
        )
        or os.environ.get("VERIDIAN_0080_TEST_INSTALL")
        != "ISOLATED_SQLITE_MEMORY"
    ):
        raise RuntimeError(
            "SAFETY STOP: Named-catalog migration 0080 is restricted "
            "to explicitly authorized in-memory SQLite tests."
        )


def refuse_reverse(apps, schema_editor):
    raise RuntimeError(
        "SAFETY STOP: Automatic removal of catalog history is prohibited."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0079_receipt_outbox_immutability"),
    ]

    operations = [
        migrations.RunPython(
            verify_isolated_catalog_install,
            migrations.RunPython.noop,
        ),
        migrations.CreateModel(
            name="ProductCatalogCollection",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        primary_key=True, default=uuid.uuid4,
                        editable=False, serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("name", models.CharField(max_length=120, unique=True)),
                ("description", models.CharField(max_length=500, blank=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="product_catalog_collections_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="ProductCatalogMembership",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        primary_key=True, default=uuid.uuid4,
                        editable=False, serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "catalog",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="memberships",
                        to="core.productcatalogcollection",
                    ),
                ),
                (
                    "equipment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="catalog_membership",
                        to="core.equipmentcatalogitem",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="product_catalog_memberships_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]

    # Forward-only protected foundation. Operational adoption
    # requires separate authorization and a reviewed migration path.
