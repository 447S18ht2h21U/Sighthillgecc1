"""Database-free regression tests for Marketing MSR read policy."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from .models import Role
from .access_marketing_msr_policy import (
    marketing_msr_read_permitted,
    marketing_msr_write_permitted,
    marketing_msr_financial_access_permitted,
    marketing_msr_signing_permitted,
)


class MarketingMSRPolicyTests(SimpleTestCase):

    def actor(self, role=Role.MARKETING, active=True, authenticated=True):
        return SimpleNamespace(
            role=role,
            is_active=active,
            is_authenticated=authenticated,
        )

    def test_active_marketing_can_request_msr_list(self):
        self.assertTrue(marketing_msr_read_permitted(
            self.actor(), action="list", method="GET"
        ))

    def test_active_marketing_can_request_msr_detail(self):
        self.assertTrue(marketing_msr_read_permitted(
            self.actor(), action="retrieve", method="GET"
        ))

    def test_unauthenticated_account_denied(self):
        self.assertFalse(marketing_msr_read_permitted(
            self.actor(authenticated=False),
            action="list", method="GET"
        ))

    def test_inactive_account_denied(self):
        self.assertFalse(marketing_msr_read_permitted(
            self.actor(active=False),
            action="list", method="GET"
        ))

    def test_missing_actor_denied(self):
        self.assertFalse(marketing_msr_read_permitted(
            None, action="list", method="GET"
        ))

    def test_other_role_not_treated_as_marketing(self):
        for role in Role.values:
            if role == Role.MARKETING:
                continue
            with self.subTest(role=role):
                self.assertFalse(marketing_msr_read_permitted(
                    self.actor(role=role),
                    action="list", method="GET"
                ))

    def test_post_actions_denied(self):
        for action in (
            "create",
            "update",
            "partial_update",
            "destroy",
            "prepare_signing",
            "prepare_document",
            "transition",
            "revision",
        ):
            with self.subTest(action=action):
                self.assertFalse(marketing_msr_read_permitted(
                    self.actor(), action=action, method="POST"
                ))

    def test_non_read_methods_denied(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
            with self.subTest(method=method):
                self.assertFalse(marketing_msr_read_permitted(
                    self.actor(), action="list", method=method
                ))

    def test_unknown_action_denied(self):
        self.assertFalse(marketing_msr_read_permitted(
            self.actor(), action="unknown", method="GET"
        ))

    def test_no_edit_authority(self):
        self.assertFalse(marketing_msr_write_permitted(self.actor()))

    def test_no_financial_authority(self):
        self.assertFalse(marketing_msr_financial_access_permitted(
            self.actor()
        ))

    def test_no_signing_authority(self):
        self.assertFalse(marketing_msr_signing_permitted(self.actor()))