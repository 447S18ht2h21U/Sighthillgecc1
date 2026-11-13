"""Isolated HTTP acceptance for CSV preview and confirmed import."""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import (
    AuditEvent, AuditHead, EquipmentCatalogItem,
    ProductCatalogCollection, Role, User,
)

URL = "/api/development-product-catalogs/bulk-csv/"
CSV = (
    "brand,residential_system_type,model_number,description\n"
    "Ruud,Heat Pump,RD-4671-A,Test system A\n"
    "Goodman,Air Conditioner,GM-4671-B,Test system B\n"
)


@override_settings(DEBUG=True)
class BulkCatalogAPIAcceptance4671(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="catalog_api_manager_4671",
            role=Role.SALES_MANAGER,
            initials="CA",
        )
        cls.associate = User.objects.create_user(
            username="catalog_api_associate_4671",
            role=Role.SALES_ASSOCIATE,
            initials="AS",
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)
        self.client = APIClient()
        self.client.force_authenticate(user=self.manager)

    def payload(self, action="preview", confirmation=None):
        return {
            "action": action,
            "name": "Reusable Catalog 4671",
            "description": "Disposable catalog acceptance",
            "catalog_id": None,
            "csv_text": CSV,
            "confirmation": confirmation,
        }

    def test_readiness_reports_disposable_only(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["available"])

    def test_preview_is_read_only(self):
        response = self.client.post(
            URL, self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_confirmation_import_creates_audited_items(self):
        preview = self.client.post(
            URL, self.payload(), format="json"
        )
        self.assertEqual(preview.status_code, 200)

        result = self.client.post(
            URL,
            self.payload("import", preview.data["confirmation"]),
            format="json",
        )
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.data["added"], 2)
        self.assertEqual(EquipmentCatalogItem.objects.count(), 2)
        self.assertEqual(AuditEvent.objects.count(), 5)

    def test_unconfirmed_import_denied(self):
        result = self.client.post(
            URL, self.payload("import"), format="json"
        )
        self.assertEqual(result.status_code, 400)
        self.assertEqual(ProductCatalogCollection.objects.count(), 0)

    def test_changed_csv_after_preview_denied(self):
        preview = self.client.post(
            URL, self.payload(), format="json"
        )
        altered = self.payload(
            "import", preview.data["confirmation"]
        )
        altered["csv_text"] += (
            "Ruud,Furnace,RD-4671-C,New system\n"
        )
        result = self.client.post(URL, altered, format="json")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)

    def test_associate_cannot_preview_or_import(self):
        self.client.force_authenticate(user=self.associate)
        self.assertEqual(
            self.client.post(
                URL, self.payload(), format="json"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(URL).status_code,
            403,
        )
