"""Permanent tests for residential equipment catalog policy."""

from types import SimpleNamespace
from unittest import TestCase

from .models import Role
from .equipment_catalog_policy import (
    EquipmentDetails,
    equipment_snapshot,
    manager_may_manage_equipment,
    validate_equipment_details,
)


class EquipmentCatalogPolicyTests(TestCase):
    def setUp(self):
        self.values = {
            "brand": "Goodman",
            "residential_system_type": "Heat Pumps (R-32)",
            "model_number": "GZV9S",
            "description": "Up to 21.0 SEER2 | Up to 10.0 HSPF2",
        }

    def actor(self, role, *, active=True, authenticated=True):
        return SimpleNamespace(
            role=role,
            is_active=active,
            is_authenticated=authenticated,
        )

    def test_sales_manager_can_manage_catalog(self):
        self.assertTrue(manager_may_manage_equipment(
            self.actor(Role.SALES_MANAGER)
        ))

    def test_installation_manager_can_manage_catalog(self):
        self.assertTrue(manager_may_manage_equipment(
            self.actor(Role.INSTALLATION_MANAGER)
        ))

    def test_sales_associate_cannot_manage_catalog(self):
        self.assertFalse(manager_may_manage_equipment(
            self.actor(Role.SALES_ASSOCIATE)
        ))

    def test_other_roles_cannot_manage_catalog(self):
        for role in (Role.TECHNICIAN, Role.MARKETING, Role.CEO):
            self.assertFalse(manager_may_manage_equipment(
                self.actor(role)
            ))

    def test_inactive_or_unauthenticated_manager_denied(self):
        self.assertFalse(manager_may_manage_equipment(
            self.actor(Role.SALES_MANAGER, active=False)
        ))
        self.assertFalse(manager_may_manage_equipment(
            self.actor(Role.INSTALLATION_MANAGER, authenticated=False)
        ))
        self.assertFalse(manager_may_manage_equipment(None))

    def test_all_four_manual_entry_fields_preserved(self):
        result = validate_equipment_details(self.values)
        self.assertIsInstance(result, EquipmentDetails)
        self.assertEqual(result.snapshot(), self.values)

    def test_missing_extra_or_empty_field_denied(self):
        for changes in (
            {"brand": ""},
            {"model_number": "  "},
            {"description": None},
            {"brand": "Goodman", "unknown": "x"},
        ):
            values = dict(self.values)
            values.update(changes)
            with self.assertRaises(ValueError):
                validate_equipment_details(values)
        values = dict(self.values)
        del values["description"]
        with self.assertRaises(ValueError):
            validate_equipment_details(values)

    def test_model_family_wildcard_is_preserved(self):
        values = dict(self.values)
        values["model_number"] = "AMST*13"
        self.assertEqual(
            validate_equipment_details(values).model_number,
            "AMST*13",
        )

    def test_snapshot_does_not_follow_later_input_changes(self):
        details = validate_equipment_details(self.values)
        snapshot = equipment_snapshot(details)
        self.values["description"] = "Later catalog revision"
        snapshot["brand"] = "Changed copy"
        self.assertEqual(details.brand, "Goodman")
        self.assertEqual(
            details.description,
            "Up to 21.0 SEER2 | Up to 10.0 HSPF2",
        )

    def test_control_characters_and_long_values_rejected(self):
        for field, value in (
            ("model_number", "X\nY"),
            ("brand", "G" * 121),
            ("description", "D" * 1001),
        ):
            values = dict(self.values)
            values[field] = value
            with self.assertRaises(ValueError):
                validate_equipment_details(values)