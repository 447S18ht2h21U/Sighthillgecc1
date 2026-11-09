"""Database-level equipment history protection in disposable SQLite."""

from django.db import DatabaseError, connection, transaction
from django.test import TestCase

from .models import EquipmentCatalogItem, Role, User


class EquipmentCatalogDatabaseIntegrityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="equipment_integrity_manager_3905",
            role=Role.SALES_MANAGER,
            initials="EIG",
        )

    def make_item(self):
        return EquipmentCatalogItem.objects.create(
            brand="Goodman",
            residential_system_type="Heat Pumps (R-32)",
            model_number="GZV9S",
            description="Up to 21.0 SEER2 | Up to 10.0 HSPF2",
            created_by=self.manager,
        )

    def test_bulk_description_rewrite_blocked(self):
        item = self.make_item()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                EquipmentCatalogItem.objects.filter(pk=item.pk).update(
                    description="Unauthorized changed specification"
                )
        item.refresh_from_db()
        self.assertEqual(
            item.description,
            "Up to 21.0 SEER2 | Up to 10.0 HSPF2",
        )

    def test_bulk_delete_and_reactivation_blocked(self):
        item = self.make_item()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                EquipmentCatalogItem.objects.filter(pk=item.pk).delete()

        EquipmentCatalogItem.objects.filter(pk=item.pk).update(
            is_active=False
        )
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                EquipmentCatalogItem.objects.filter(pk=item.pk).update(
                    is_active=True
                )
        item.refresh_from_db()
        self.assertFalse(item.is_active)

    def test_deactivation_permitted_and_two_guards_installed(self):
        item = self.make_item()
        changed = EquipmentCatalogItem.objects.filter(
            pk=item.pk
        ).update(is_active=False)
        self.assertEqual(changed, 1)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='trigger' AND name LIKE 'equipment_history_%_guard'"
            )
            names = {row[0] for row in cursor.fetchall()}
        self.assertEqual(names, {
            "equipment_history_update_guard",
            "equipment_history_delete_guard",
        })