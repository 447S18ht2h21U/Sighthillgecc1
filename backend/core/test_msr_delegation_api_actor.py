"""Mocked actor verification; no test DB, migrations or live routes."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from rest_framework.exceptions import PermissionDenied

from core.models import Role
from core.msr_delegation_api_actor import (
    verified_delegation_actor,
    actor_verification_grants_live_msr_access,
)


class DelegationActorTests(unittest.TestCase):
    def setUp(self):
        self.identifier = uuid4()
        self.session = SimpleNamespace(
            pk=self.identifier,
            is_authenticated=True,
            role=Role.CEO,
            is_active=True,
        )
        self.request = SimpleNamespace(user=self.session)

    def check(self, action, stored_role, *, active=True):
        verified = SimpleNamespace(
            pk=self.identifier, role=stored_role, is_active=active
        )
        with patch(
            "core.msr_delegation_api_actor.User.objects.filter"
        ) as lookup:
            lookup.return_value.first.return_value = (
                verified if active else None
            )
            result = verified_delegation_actor(
                self.request, action=action
            )
            lookup.assert_called_once_with(
                pk=self.identifier, is_active=True
            )
        return result

    def test_manager_can_pass_request_role_gate(self):
        self.assertEqual(
            self.check("request", Role.SALES_MANAGER).pk,
            self.identifier,
        )

    def test_ceo_can_pass_approval_role_gate(self):
        self.assertEqual(
            self.check("approve", Role.CEO).pk,
            self.identifier,
        )

    def test_comptroller_can_pass_approval_role_gate(self):
        self.check("approve", Role.COMPTROLLER)

    def test_sales_associate_can_pass_surrender_gate(self):
        self.check("surrender", Role.SALES_ASSOCIATE)

    def test_executive_can_pass_revocation_role_gate(self):
        self.check("revoke", Role.COMPTROLLER)

    def test_only_comptroller_passes_reassignment_gate(self):
        self.check("reassign", Role.COMPTROLLER)
        with patch(
            "core.msr_delegation_api_actor.User.objects.filter"
        ) as lookup:
            lookup.return_value.first.return_value = SimpleNamespace(
                pk=self.identifier, role=Role.CEO, is_active=True
            )
            with self.assertRaises(PermissionDenied):
                verified_delegation_actor(
                    self.request, action="reassign"
                )

    def test_session_role_cannot_override_database_role(self):
        with patch(
            "core.msr_delegation_api_actor.User.objects.filter"
        ) as lookup:
            lookup.return_value.first.return_value = SimpleNamespace(
                pk=self.identifier,
                role=Role.SALES_ASSOCIATE,
                is_active=True,
            )
            with self.assertRaises(PermissionDenied):
                verified_delegation_actor(
                    self.request, action="approve"
                )

    def test_inactive_database_user_rejected(self):
        with patch(
            "core.msr_delegation_api_actor.User.objects.filter"
        ) as lookup:
            lookup.return_value.first.return_value = None
            with self.assertRaises(PermissionDenied):
                verified_delegation_actor(
                    self.request, action="approve"
                )

    def test_anonymous_user_rejected_without_lookup(self):
        self.session.is_authenticated = False
        with patch(
            "core.msr_delegation_api_actor.User.objects.filter"
        ) as lookup:
            with self.assertRaises(PermissionDenied):
                verified_delegation_actor(
                    self.request, action="approve"
                )
            lookup.assert_not_called()

    def test_missing_identity_rejected(self):
        self.session.pk = None
        with self.assertRaises(PermissionDenied):
            verified_delegation_actor(
                self.request, action="request"
            )

    def test_unknown_action_denied_without_lookup(self):
        with patch(
            "core.msr_delegation_api_actor.User.objects.filter"
        ) as lookup:
            with self.assertRaises(PermissionDenied):
                verified_delegation_actor(
                    self.request, action="admin"
                )
            lookup.assert_not_called()

    def test_client_supplied_actor_is_not_accepted(self):
        with self.assertRaises(TypeError):
            verified_delegation_actor(
                self.request,
                action="approve",
                actor_id=uuid4(),
            )

    def test_different_database_identity_rejected(self):
        with patch(
            "core.msr_delegation_api_actor.User.objects.filter"
        ) as lookup:
            lookup.return_value.first.return_value = SimpleNamespace(
                pk=uuid4(), role=Role.CEO, is_active=True
            )
            with self.assertRaises(PermissionDenied):
                verified_delegation_actor(
                    self.request, action="approve"
                )

    def test_actor_gate_does_not_activate_live_access(self):
        self.assertIs(
            actor_verification_grants_live_msr_access(), False
        )


if __name__ == "__main__":
    unittest.main()