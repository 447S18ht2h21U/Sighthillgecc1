"""Isolated acceptance for persistent import activation contract."""
from unittest.mock import patch

from django.test import TestCase

from . import catalog_bulk_import_service_4670 as service
from .catalog_persistent_activation_policy_4688 import (
    require_persistent_catalog_activation,
)
from .models import (
    AuditEvent,
    AuditHead,
    EquipmentCatalogItem,
    Outbox,
    ProductCatalogCollection,
    ProductCatalogMembership,
    Role,
    User,
)

HEADER = "brand,residential_system_type,model_number,description\n"


def fixture():
    return (
        HEADER
        + "Lennox,Heat Pump,LX-4688-A,First test product\n"
        + "Lennox,Furnace,LX-4688-B,Second test product\n"
    ).encode("utf-8")


class PersistentCatalogPolicy4688Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="catalog_manager_4688",
            role=Role.SALES_MANAGER,
            initials="CM",
        )
        cls.associate = User.objects.create_user(
            username="catalog_associate_4688",
            role=Role.SALES_ASSOCIATE,
            initials="CA",
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)

    def test_policy_default_deny(self):
        with self.assertRaisesRegex(RuntimeError, "not activated"):
            require_persistent_catalog_activation()

    def test_environment_variable_cannot_enable_import(self):
        with patch.dict(
            "os.environ",
            {"VERIDIAN_CATALOG_IMPORT_ENABLED": "1"},
        ):
            with self.assertRaisesRegex(RuntimeError, "not activated"):
                service.import_catalog_csv_persistent(
                    actor_id=self.manager.pk,
                    content=fixture(),
                    name="Lennox Test",
                    description="Disposable test",
                )

        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_authorized_transaction_reuses_existing_services(self):
        # Simulate a future authorization only in disposable memory.
        # The installed policy constant remains False.
        with patch.object(
            service,
            "_require_persistent_import_authorization",
            return_value=None,
        ):
            catalog, count = service.import_catalog_csv_persistent(
                actor_id=self.manager.pk,
                content=fixture(),
                name="Lennox Test",
                description="Disposable test",
            )

        self.assertEqual(count, 2)
        self.assertEqual(catalog.name, "Lennox Test")
        self.assertEqual(EquipmentCatalogItem.objects.count(), 2)
        self.assertEqual(ProductCatalogCollection.objects.count(), 1)
        self.assertEqual(ProductCatalogMembership.objects.count(), 2)
        self.assertEqual(AuditEvent.objects.count(), 5)
        self.assertEqual(Outbox.objects.count(), 5)

    def test_unauthorized_role_denied_after_gate(self):
        from django.core.exceptions import PermissionDenied

        with patch.object(
            service,
            "_require_persistent_import_authorization",
            return_value=None,
        ):
            with self.assertRaises(PermissionDenied):
                service.import_catalog_csv_persistent(
                    actor_id=self.associate.pk,
                    content=fixture(),
                    name="Denied Catalog",
                    description="Disposable test",
                )

        self.assertEqual(ProductCatalogCollection.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)
