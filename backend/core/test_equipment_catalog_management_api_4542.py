"""Manager catalog API contract and authorization regression."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from .equipment_catalog_management_api_4542 import (
    manage_catalog, manage_catalog_item,
)

FIELDS = {
    "brand": "Fictional",
    "residential_system_type": "Heat Pump",
    "model_number": "TEST-01",
    "description": "Fictional test equipment",
}


@override_settings(DEBUG=True, ENVIRONMENT="development")
class CatalogManagement4542Tests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def request(self, method="GET", role="SALES_MANAGER", data=None):
        path = "/api/development-equipment-management/"
        if method == "POST":
            req = self.factory.post(path, data=data, format="json")
        elif method == "PATCH":
            req = self.factory.patch(path, data=data, format="json")
        elif method == "DELETE":
            req = self.factory.delete(path, data=data, format="json")
        else:
            req = self.factory.get(path)
        force_authenticate(req, user=SimpleNamespace(
            pk=uuid4(), role=role, is_active=True,
            is_authenticated=True,
        ))
        return req

    def test_sales_associate_cannot_add(self):
        with patch(
            "core.equipment_catalog_management_api_4542.create_equipment"
        ) as create:
            result = manage_catalog(
                self.request("POST", "SALES_ASSOCIATE", FIELDS)
            )
        self.assertEqual(result.status_code, 403)
        create.assert_not_called()

    def test_comptroller_cannot_change_catalog(self):
        result = manage_catalog(self.request("POST", "COMPTROLLER", FIELDS))
        self.assertEqual(result.status_code, 403)

    def test_sales_manager_can_add_through_existing_service(self):
        item = SimpleNamespace(pk=uuid4(), revision=1, is_active=True)
        with patch(
            "core.equipment_catalog_management_api_4542.create_equipment",
            return_value=item,
        ) as create:
            result = manage_catalog(self.request("POST", data=FIELDS))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["id"], str(item.pk))
        self.assertEqual(create.call_args.kwargs["fields"], FIELDS)

    def test_installation_manager_can_revise(self):
        item = SimpleNamespace(pk=uuid4(), revision=2, is_active=True)
        with patch(
            "core.equipment_catalog_management_api_4542.revise_equipment",
            return_value=item,
        ) as revise:
            result = manage_catalog_item(
                self.request("PATCH", "INSTALLATION_MANAGER", FIELDS),
                uuid4(),
            )
        self.assertEqual(result.status_code, 200)
        revise.assert_called_once()

    def test_manager_deactivation_requires_reason_field(self):
        result = manage_catalog_item(
            self.request("DELETE", data={}), uuid4()
        )
        self.assertEqual(result.status_code, 400)

    def test_manager_deactivation_uses_service(self):
        item = SimpleNamespace(pk=uuid4(), revision=1, is_active=False)
        with patch(
            "core.equipment_catalog_management_api_4542.deactivate_equipment",
            return_value=item,
        ) as deactivate:
            result = manage_catalog_item(
                self.request("DELETE", data={"reason": "Discontinued test product"}),
                uuid4(),
            )
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.data["is_active"])
        deactivate.assert_called_once()

    def test_unknown_fields_rejected(self):
        result = manage_catalog(self.request("POST", data={
            **FIELDS, "is_active": True,
        }))
        self.assertEqual(result.status_code, 400)

    def test_read_only_selection_not_used_for_mutations(self):
        result = manage_catalog_item(
            self.request("PATCH", "SALES_ASSOCIATE", FIELDS),
            uuid4(),
        )
        self.assertEqual(result.status_code, 403)
