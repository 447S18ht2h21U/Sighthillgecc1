"""Protected foundation tests for independent named product catalogs."""

from django.test import SimpleTestCase, TestCase

from .models import (
    EquipmentCatalogItem,
    ProductCatalogCollection,
    ProductCatalogMembership,
)


class NamedCatalogStructure4545Tests(SimpleTestCase):
    def test_catalog_name_is_unique(self):
        field = ProductCatalogCollection._meta.get_field("name")
        self.assertTrue(field.unique)
        self.assertEqual(field.max_length, 120)

    def test_catalog_has_deactivation_status(self):
        field = ProductCatalogCollection._meta.get_field("is_active")
        self.assertTrue(field.default)

    def test_equipment_revision_has_at_most_one_catalog(self):
        field = ProductCatalogMembership._meta.get_field("equipment")
        self.assertTrue(field.one_to_one)

    def test_catalog_membership_protects_references(self):
        from django.db.models import PROTECT
        self.assertIs(
            ProductCatalogMembership._meta.get_field("equipment").remote_field.on_delete,
            PROTECT,
        )
        self.assertIs(
            ProductCatalogMembership._meta.get_field("catalog").remote_field.on_delete,
            PROTECT,
        )

    def test_legacy_equipment_model_still_exists(self):
        self.assertEqual(
            EquipmentCatalogItem._meta.db_table,
            "core_equipmentcatalogitem",
        )


class NamedCatalogDatabase4545Tests(TestCase):
    def test_disposable_schema_contains_new_tables(self):
        from django.db import connection
        tables = set(connection.introspection.table_names())
        self.assertIn("core_productcatalogcollection", tables)
        self.assertIn("core_productcatalogmembership", tables)
