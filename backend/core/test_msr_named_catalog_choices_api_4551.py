"""Role gates and response isolation for the MSR catalog picker."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from .msr_named_catalog_choices_api_4551 import (
    msr_named_catalog_choices,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class MSRNamedCatalogChoices4551Tests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def request(self, role="SALES_ASSOCIATE", active=True, method="GET"):
        path = "/api/development-msr-named-catalogs/"
        if method == "POST":
            request = self.factory.post(path, {}, format="json")
        else:
            request = self.factory.get(path)
        force_authenticate(request, user=SimpleNamespace(
            pk=uuid4(),
            role=role,
            is_active=active,
            is_authenticated=True,
        ))
        return request

    def test_route_registered(self):
        self.assertEqual(
            resolve("/api/development-msr-named-catalogs/").func.cls,
            msr_named_catalog_choices.cls,
        )

    def test_sales_associate_can_read(self):
        rows = [{"id": "sample", "name": "TEST HVAC", "products": []}]
        with patch(
            "core.msr_named_catalog_choices_api_4551._load_catalog_choices",
            return_value=rows,
        ) as load:
            result = msr_named_catalog_choices(self.request())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data, rows)
        load.assert_called_once_with()

    def test_installation_manager_can_read(self):
        with patch(
            "core.msr_named_catalog_choices_api_4551._load_catalog_choices",
            return_value=[],
        ):
            result = msr_named_catalog_choices(
                self.request("INSTALLATION_MANAGER")
            )
        self.assertEqual(result.status_code, 200)

    def test_technician_denied(self):
        result = msr_named_catalog_choices(self.request("TECHNICIAN"))
        self.assertEqual(result.status_code, 404)

    def test_inactive_user_denied(self):
        result = msr_named_catalog_choices(
            self.request("SALES_MANAGER", active=False)
        )
        self.assertEqual(result.status_code, 404)

    @override_settings(DEBUG=False)
    def test_debug_disabled_denied(self):
        result = msr_named_catalog_choices(self.request())
        self.assertEqual(result.status_code, 404)

    def test_post_denied(self):
        result = msr_named_catalog_choices(self.request(method="POST"))
        self.assertEqual(result.status_code, 405)
