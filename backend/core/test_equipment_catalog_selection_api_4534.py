"""Isolated catalog-selection API authorization tests."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.db.utils import OperationalError
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .equipment_catalog_selection_api_4534 import equipment_catalog_choices


class CatalogSelectionAPI4534Tests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def request(self, role="SALES_ASSOCIATE", authenticate=True):
        req = self.factory.get("/api/development-equipment-catalog/")
        if authenticate:
            force_authenticate(req, user=SimpleNamespace(
                pk=uuid4(), role=role,
                is_active=True, is_authenticated=True,
            ))
        return req

    @override_settings(DEBUG=True)
    def test_authorized_read_returns_catalog_snapshots(self):
        row = {
            "id": uuid4(),
            "brand": "FICTIONAL BRAND",
            "residential_system_type": "Heat Pump",
            "model_number": "TEST-ONLY",
            "description": "FICTIONAL EQUIPMENT",
        }
        with patch(
            "core.equipment_catalog_selection_api_4534.EquipmentCatalogItem"
        ) as model:
            query = model.objects.filter.return_value
            query = query.order_by.return_value
            query = query.values.return_value
            query.__getitem__.return_value = [row]
            result = equipment_catalog_choices(self.request())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data[0]["id"], str(row["id"]))
        self.assertEqual(result.data[0]["model_number"], "TEST-ONLY")
        self.assertIn("no-store", result["Cache-Control"])

    @override_settings(DEBUG=True)
    def test_manager_can_read(self):
        with patch(
            "core.equipment_catalog_selection_api_4534.EquipmentCatalogItem"
        ) as model:
            query = model.objects.filter.return_value
            query = query.order_by.return_value
            query = query.values.return_value
            query.__getitem__.return_value = []
            result = equipment_catalog_choices(
                self.request(role="INSTALLATION_MANAGER")
            )
        self.assertEqual(result.status_code, 200)

    @override_settings(DEBUG=True)
    def test_unauthorized_roles_denied(self):
        for role in ("TECHNICIAN", "DBA", "AP_ASSOCIATE"):
            with self.subTest(role=role):
                self.assertEqual(
                    equipment_catalog_choices(
                        self.request(role=role)
                    ).status_code, 404
                )

    @override_settings(DEBUG=True)
    def test_anonymous_denied(self):
        result = equipment_catalog_choices(
            self.request(authenticate=False)
        )
        self.assertIn(result.status_code, (401, 403))

    @override_settings(DEBUG=False)
    def test_debug_disabled_denied(self):
        self.assertEqual(
            equipment_catalog_choices(self.request()).status_code, 404
        )

    @override_settings(DEBUG=True, ENVIRONMENT="production")
    def test_production_denied(self):
        self.assertEqual(
            equipment_catalog_choices(self.request()).status_code, 404
        )

    @override_settings(DEBUG=True)
    def test_missing_catalog_table_returns_controlled_error(self):
        with patch(
            "core.equipment_catalog_selection_api_4534.EquipmentCatalogItem"
        ) as model:
            query = model.objects.filter.return_value
            query = query.order_by.return_value
            query = query.values.return_value
            query.__getitem__.side_effect = OperationalError(
                "no such table: core_equipmentcatalogitem"
            )
            result = equipment_catalog_choices(self.request())
        self.assertEqual(result.status_code, 503)
        self.assertEqual(
            result.data["detail"],
            "Equipment catalog database is not activated."
        )

    @override_settings(DEBUG=True)
    def test_post_denied(self):
        req = self.factory.post("/api/development-equipment-catalog/")
        force_authenticate(req, user=SimpleNamespace(
            pk=uuid4(), role="SALES_MANAGER",
            is_active=True, is_authenticated=True,
        ))
        result = equipment_catalog_choices(req)
        self.assertEqual(result.status_code, 405)
