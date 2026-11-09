"""Development-only named catalog API authorization and routing tests."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from .product_catalog_collections_api_4546 import (
    collections,
    collection_detail,
    collection_products,
    collection_product_detail,
)

FIELDS = {
    "brand": "FICTIONAL",
    "residential_system_type": "Heat Pump",
    "model_number": "SAMPLE-001",
    "description": "Fictional test unit",
}


@override_settings(DEBUG=True, ENVIRONMENT="development")
class NamedCatalogApi4546Tests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def request(self, method="GET", role="SALES_MANAGER", data=None):
        path = "/api/development-product-catalogs/"
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

    def test_routes_register(self):
        self.assertEqual(
            resolve("/api/development-product-catalogs/").func.cls,
            collections.cls,
        )

    def test_sales_associate_cannot_create_catalog(self):
        result = collections(self.request(
            "POST", "SALES_ASSOCIATE",
            {"name": "Sample", "description": ""},
        ))
        self.assertEqual(result.status_code, 403)

    def test_comptroller_cannot_create_catalog(self):
        result = collections(self.request(
            "POST", "COMPTROLLER",
            {"name": "Sample", "description": ""},
        ))
        self.assertEqual(result.status_code, 403)

    def test_manager_can_create_catalog(self):
        sample = SimpleNamespace(
            pk=uuid4(), name="Sample", description="", is_active=True
        )
        with patch(
            "core.product_catalog_collections_api_4546.create_named_catalog",
            return_value=sample,
        ) as create:
            result = collections(self.request(
                "POST", data={"name": "Sample", "description": ""},
            ))
        self.assertEqual(result.status_code, 201)
        create.assert_called_once()

    def test_installation_manager_can_create_product(self):
        item = SimpleNamespace(pk=uuid4(), revision=1, is_active=True)
        with patch(
            "core.product_catalog_collections_api_4546.create_catalog_product",
            return_value=item,
        ) as create:
            result = collection_products(
                self.request("POST", "INSTALLATION_MANAGER", FIELDS),
                uuid4(),
            )
        self.assertEqual(result.status_code, 201)
        create.assert_called_once()

    def test_unknown_equipment_field_rejected(self):
        result = collection_products(
            self.request("POST", data={**FIELDS, "is_active": True}),
            uuid4(),
        )
        self.assertEqual(result.status_code, 400)

    def test_revision_service_used(self):
        item = SimpleNamespace(pk=uuid4(), revision=2, is_active=True)
        with patch(
            "core.product_catalog_collections_api_4546.revise_catalog_product",
            return_value=item,
        ) as revise:
            result = collection_product_detail(
                self.request("PATCH", data=FIELDS),
                uuid4(), uuid4(),
            )
        self.assertEqual(result.status_code, 200)
        revise.assert_called_once()

    def test_catalog_deactivation_requires_reason(self):
        result = collection_detail(
            self.request("DELETE", data={}), uuid4()
        )
        self.assertEqual(result.status_code, 400)

    def test_product_deactivation_requires_reason(self):
        result = collection_product_detail(
            self.request("DELETE", data={}), uuid4(), uuid4()
        )
        self.assertEqual(result.status_code, 400)

    def test_sales_associate_cannot_revise(self):
        result = collection_product_detail(
            self.request("PATCH", "SALES_ASSOCIATE", FIELDS),
            uuid4(), uuid4(),
        )
        self.assertEqual(result.status_code, 403)
