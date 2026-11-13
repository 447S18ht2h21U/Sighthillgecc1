"""Ruud catalog import acceptance in disposable SQLite only.

This tests the real audited named-catalog services without touching
the operational or persistent development database.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from .models import (
    AuditEvent,
    AuditHead,
    EquipmentCatalogItem,
    ProductCatalogCollection,
    ProductCatalogMembership,
    Role,
    User,
)
from .product_catalog_collections_service_4546 import (
    create_named_catalog,
    create_catalog_product,
)


SOURCE = (
    Path(settings.BASE_DIR)
    / "core"
    / "catalog_sources"
    / "ruud_2026_20261113.json"
)


class RuudCatalogIntegrationAcceptance4648(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="ruud_manager_4648",
            role=Role.SALES_MANAGER,
            initials="RM",
        )
        cls.installation_manager = User.objects.create_user(
            username="ruud_installation_4648",
            role=Role.INSTALLATION_MANAGER,
            initials="RI",
        )
        cls.associate = User.objects.create_user(
            username="ruud_associate_4648",
            role=Role.SALES_ASSOCIATE,
            initials="RA",
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)

        self.manifest = json.loads(
            SOURCE.read_text(encoding="utf-8")
        )

        self.assertEqual(
            self.manifest["catalog_name"],
            "Ruud Residential Systems",
        )
        self.assertEqual(self.manifest["equipment_count"], 15)
        self.assertEqual(len(self.manifest["records"]), 15)
        self.assertEqual(
            len({
                row["ahri_reference"]
                for row in self.manifest["records"]
            }),
            15,
        )

    def make_catalog(self):
        return create_named_catalog(
            actor_id=self.manager.pk,
            name=self.manifest["catalog_name"],
            description=self.manifest["catalog_description"],
        )

    def import_rows(self, catalog):
        return [
            create_catalog_product(
                actor_id=self.manager.pk,
                catalog_id=catalog.pk,
                fields=dict(row["catalog_fields"]),
            )
            for row in self.manifest["records"]
        ]

    def test_all_15_combinations_are_imported_and_audited(self):
        catalog = self.make_catalog()
        created = self.import_rows(catalog)

        self.assertTrue(catalog.is_active)
        self.assertEqual(len(created), 15)
        self.assertEqual(
            ProductCatalogCollection.objects.count(), 1
        )
        self.assertEqual(
            EquipmentCatalogItem.objects.count(), 15
        )
        self.assertEqual(
            ProductCatalogMembership.objects.filter(
                catalog=catalog
            ).count(),
            15,
        )

        self.assertEqual(
            AuditEvent.objects.filter(
                action="product.catalog.collection.created"
            ).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                action="equipment.catalog.created"
            ).count(),
            15,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                action="product.catalog.membership.created"
            ).count(),
            15,
        )

        for row, item in zip(self.manifest["records"], created):
            fields = row["catalog_fields"]

            self.assertEqual(item.brand, "Ruud")
            self.assertEqual(
                item.residential_system_type,
                fields["residential_system_type"],
            )
            self.assertEqual(item.model_number, fields["model_number"])
            self.assertEqual(item.description, fields["description"])
            self.assertTrue(item.is_active)

            for value in (
                row["ahri_reference"],
                row["outdoor_model"],
                row["coil_model"],
                row["furnace_model"],
                str(row["capacity_btuh"]),
                row["seer2"],
            ):
                self.assertIn(value, item.description)

            self.assertIn(
                row["outdoor_model"], item.model_number
            )
            self.assertIn(
                row["coil_model"], item.model_number
            )
            self.assertIn(
                row["furnace_model"], item.model_number
            )

        print("PASS: All 15 Ruud systems and audit records verified.")

    def test_duplicate_import_cannot_create_duplicate_systems(self):
        catalog = self.make_catalog()
        self.import_rows(catalog)

        first = self.manifest["records"][0]

        with self.assertRaises(ValidationError):
            create_catalog_product(
                actor_id=self.manager.pk,
                catalog_id=catalog.pk,
                fields=dict(first["catalog_fields"]),
            )

        self.assertEqual(
            EquipmentCatalogItem.objects.count(), 15
        )
        self.assertEqual(
            ProductCatalogMembership.objects.count(), 15
        )

        print("PASS: Duplicate equipment identity rejected.")

    def test_unauthorized_employee_cannot_import_equipment(self):
        catalog = self.make_catalog()

        with self.assertRaises(PermissionDenied):
            create_catalog_product(
                actor_id=self.associate.pk,
                catalog_id=catalog.pk,
                fields=dict(
                    self.manifest["records"][0]["catalog_fields"]
                ),
            )

        self.assertFalse(
            EquipmentCatalogItem.objects.exists()
        )

        print("PASS: Sales Associate catalog writes denied.")

    def test_installation_manager_can_manage_ruud_equipment(self):
        catalog = self.make_catalog()

        item = create_catalog_product(
            actor_id=self.installation_manager.pk,
            catalog_id=catalog.pk,
            fields=dict(
                self.manifest["records"][0]["catalog_fields"]
            ),
        )

        self.assertEqual(item.brand, "Ruud")
        self.assertEqual(
            item.created_by_id,
            self.installation_manager.pk,
        )

        print("PASS: Installation Manager catalog authority verified.")

    def test_goodman_catalog_remains_independent(self):
        goodman = create_named_catalog(
            actor_id=self.manager.pk,
            name="Goodman Residential",
            description="Partial model-family references only.",
        )

        goodman_item = create_catalog_product(
            actor_id=self.manager.pk,
            catalog_id=goodman.pk,
            fields={
                "brand": "Goodman",
                "residential_system_type": "Heat Pump",
                "model_number": "GOODMAN-FAMILY-TEST",
                "description": (
                    "Synthetic partial model-family reference; "
                    "AHRI not available."
                ),
            },
        )

        ruud = self.make_catalog()
        self.import_rows(ruud)

        goodman_item.refresh_from_db()
        self.assertTrue(goodman_item.is_active)
        self.assertEqual(
            goodman_item.description,
            "Synthetic partial model-family reference; "
            "AHRI not available.",
        )
        self.assertEqual(
            ProductCatalogMembership.objects.filter(
                catalog=goodman
            ).count(),
            1,
        )
        self.assertEqual(
            ProductCatalogMembership.objects.filter(
                catalog=ruud
            ).count(),
            15,
        )

        print("PASS: Goodman and Ruud catalogs remain independent.")
