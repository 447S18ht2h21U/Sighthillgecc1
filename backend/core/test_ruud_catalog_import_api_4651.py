"""Authenticated Ruud import API tests; disposable SQLite only."""
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import (
    AuditHead, EquipmentCatalogItem, ProductCatalogMembership,
    Role, User,
)


PATH = "/api/development-product-catalogs/import-ruud-2026/"


@override_settings(DEBUG=True)
class RuudCatalogImportAPI4651Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="ruud_api_manager_4651",
            role=Role.SALES_MANAGER,
            initials="RAM",
        )
        cls.associate = User.objects.create_user(
            username="ruud_api_associate_4651",
            role=Role.SALES_ASSOCIATE,
            initials="RAA",
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)
        self.client = APIClient()

    def test_manager_imports_and_repeat_is_idempotent(self):
        self.client.force_authenticate(user=self.manager)
        first = self.client.post(PATH, {}, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data["added"], 15)
        self.assertFalse(first.data["persistent_activation"])

        second = self.client.post(PATH, {}, format="json")
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data["added"], 0)
        self.assertEqual(EquipmentCatalogItem.objects.count(), 15)
        self.assertEqual(ProductCatalogMembership.objects.count(), 15)

    def test_sales_associate_cannot_import(self):
        self.client.force_authenticate(user=self.associate)
        response = self.client.post(PATH, {}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(EquipmentCatalogItem.objects.exists())

    def test_client_cannot_supply_equipment_overrides(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            PATH, {"brand": "Ruud"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EquipmentCatalogItem.objects.exists())

    def test_persistent_database_guard_fails_closed(self):
        self.client.force_authenticate(user=self.manager)
        with patch(
            "core.ruud_catalog_import_api_4651._require_isolated_database",
            side_effect=RuntimeError("Persistent database blocked"),
        ):
            response = self.client.post(PATH, {}, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(EquipmentCatalogItem.objects.exists())

    def test_manager_can_read_isolated_import_readiness(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(PATH)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["available"])
        self.assertEqual(response.data["system_count"], 15)
        self.assertFalse(response.data["persistent_activation"])
        self.assertFalse(EquipmentCatalogItem.objects.exists())

    def test_persistent_import_readiness_is_disabled(self):
        self.client.force_authenticate(user=self.manager)
        with patch(
            "core.ruud_catalog_import_api_4651."
            "_require_isolated_database",
            side_effect=RuntimeError("Persistent storage blocked"),
        ):
            response = self.client.get(PATH)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["available"])
        self.assertFalse(EquipmentCatalogItem.objects.exists())

    def test_associate_cannot_read_import_readiness(self):
        self.client.force_authenticate(user=self.associate)
        response = self.client.get(PATH)
        self.assertEqual(response.status_code, 403)
