"""Isolated database-backed tests of the unregistered tax boundary."""
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied
from .models import Role, User
from .tax_entry_authorization_4437I import require_tax_entry_action

class TaxEntryAuthorization4437ITests(TestCase):
    def setUp(self):
        self.comp = User.objects.create_user(username="tax_comp_4437i", password="fixture-only", role=Role.COMPTROLLER)
        self.ceo = User.objects.create_user(username="tax_ceo_4437i", password="fixture-only", role=Role.CEO)

    def test_01_active_comptroller_may_prepare_only(self):
        self.assertEqual(require_tax_entry_action(self.comp, "PREPARE_DRAFT").pk, self.comp.pk)

    def test_02_ceo_cannot_prepare(self):
        with self.assertRaises(PermissionDenied):
            require_tax_entry_action(self.ceo, "PREPARE_DRAFT")

    def test_03_inactive_account_denied(self):
        self.comp.is_active = False
        self.comp.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            require_tax_entry_action(self.comp, "PREPARE_DRAFT")

    def test_04_stale_actor_role_denied(self):
        User.objects.filter(pk=self.comp.pk).update(role=Role.CEO)
        with self.assertRaises(PermissionDenied):
            require_tax_entry_action(self.comp, "PREPARE_DRAFT")

    def test_05_unsaved_actor_denied(self):
        with self.assertRaises(PermissionDenied):
            require_tax_entry_action(User(role=Role.COMPTROLLER), "PREPARE_DRAFT")

    def test_06_all_tax_operational_actions_denied(self):
        for action in ("VERIFY", "POST", "FILE", "PAY", "APPROVE", "INCLUDE_IN_REPORT", "ADJUST", "UNKNOWN"):
            with self.subTest(action=action):
                with self.assertRaises(PermissionDenied):
                    require_tax_entry_action(self.comp, action)

    def test_07_no_actor_denied(self):
        with self.assertRaises(PermissionDenied):
            require_tax_entry_action(None, "PREPARE_DRAFT")
