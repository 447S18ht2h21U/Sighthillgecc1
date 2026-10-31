"""Database-free security regression tests for MSR visibility."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from .models import Role
from .access_msr_visibility_policy import (
    msr_read_scope,
    msr_project_read_permitted,
    msr_temporary_delegation_permitted,
    msr_read_policy_grants_write,
    msr_read_policy_grants_signing,
    msr_read_policy_grants_financial_access,
)


class MSRVisibilityPolicyTests(SimpleTestCase):

    def actor(self, role, *, pk=101, active=True, authenticated=True):
        return SimpleNamespace(
            pk=pk,
            id=pk,
            role=role,
            is_active=active,
            is_authenticated=authenticated,
        )

    def project(self, associate_id=101):
        return SimpleNamespace(
            sales_associate_id=associate_id,
        )

    def test_all_project_positions(self):
        for role in (
            Role.CEO,
            Role.COMPTROLLER,
            Role.MARKETING,
            Role.SALES_MANAGER,
            Role.INSTALLATION_MANAGER,
        ):
            with self.subTest(role=role):
                user = self.actor(role)
                self.assertEqual(
                    msr_read_scope(user, action="list", method="GET"),
                    "ALL_PROJECTS",
                )
                self.assertTrue(
                    msr_project_read_permitted(
                        user, self.project(associate_id=999),
                        action="retrieve", method="GET",
                    )
                )

    def test_assigned_project_positions(self):
        for role in (Role.SALES_ASSOCIATE, Role.TECHNICIAN):
            with self.subTest(role=role):
                self.assertEqual(
                    msr_read_scope(
                        self.actor(role), action="list", method="GET"
                    ),
                    "ASSIGNED_PROJECTS",
                )

    def test_sales_associate_own_project(self):
        self.assertTrue(
            msr_project_read_permitted(
                self.actor(Role.SALES_ASSOCIATE),
                self.project(associate_id=101),
                action="retrieve", method="GET",
            )
        )

    def test_sales_associate_other_project_denied(self):
        self.assertFalse(
            msr_project_read_permitted(
                self.actor(Role.SALES_ASSOCIATE),
                self.project(associate_id=202),
                action="retrieve", method="GET",
            )
        )

    def test_missing_ownership_denied(self):
        self.assertFalse(
            msr_project_read_permitted(
                self.actor(Role.SALES_ASSOCIATE, pk=None),
                self.project(associate_id=None),
                action="retrieve", method="GET",
            )
        )

    def test_technician_assignment_not_self_authorized(self):
        technician = self.actor(Role.TECHNICIAN)

        for evidence in (False, True):
            with self.subTest(evidence=evidence):
                self.assertFalse(
                    msr_project_read_permitted(
                        technician,
                        self.project(),
                        action="retrieve",
                        method="GET",
                        active_technician_assignment=evidence,
                    )
                )

    def test_non_msr_positions_denied(self):
        for role in (
            Role.ACCOUNTS_PAYABLE_ASSOCIATE,
            Role.DATABASE_ADMINISTRATOR,
        ):
            with self.subTest(role=role):
                user = self.actor(role)
                self.assertIsNone(
                    msr_read_scope(user, action="list", method="GET")
                )
                self.assertFalse(
                    msr_project_read_permitted(
                        user, self.project(),
                        action="retrieve", method="GET",
                    )
                )

    def test_every_position_classified(self):
        classified = {
            Role.CEO,
            Role.COMPTROLLER,
            Role.MARKETING,
            Role.SALES_MANAGER,
            Role.INSTALLATION_MANAGER,
            Role.SALES_ASSOCIATE,
            Role.TECHNICIAN,
            Role.ACCOUNTS_PAYABLE_ASSOCIATE,
            Role.DATABASE_ADMINISTRATOR,
        }
        self.assertEqual(set(Role.values), classified)

    def test_inactive_account_denied(self):
        for role in Role.values:
            with self.subTest(role=role):
                user = self.actor(role, active=False)
                self.assertIsNone(
                    msr_read_scope(user, action="list", method="GET")
                )
                self.assertFalse(
                    msr_project_read_permitted(
                        user, self.project(),
                        action="retrieve", method="GET",
                    )
                )

    def test_unauthenticated_account_denied(self):
        for role in Role.values:
            with self.subTest(role=role):
                self.assertIsNone(
                    msr_read_scope(
                        self.actor(role, authenticated=False),
                        action="list", method="GET",
                    )
                )

    def test_missing_actor_and_project_denied(self):
        self.assertIsNone(
            msr_read_scope(None, action="list", method="GET")
        )
        self.assertFalse(
            msr_project_read_permitted(
                None, self.project(),
                action="retrieve", method="GET",
            )
        )
        self.assertFalse(
            msr_project_read_permitted(
                self.actor(Role.CEO), None,
                action="retrieve", method="GET",
            )
        )

    def test_only_get_list_and_retrieve(self):
        user = self.actor(Role.CEO)

        for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
            with self.subTest(method=method):
                self.assertIsNone(
                    msr_read_scope(user, action="list", method=method)
                )

        for action in (
            "create", "update", "partial_update", "destroy",
            "change", "revision", "approve", "prepare_signing",
            "prepare_document", "download", "unknown",
        ):
            with self.subTest(action=action):
                self.assertIsNone(
                    msr_read_scope(user, action=action, method="GET")
                )

    def test_unknown_role_denied(self):
        self.assertIsNone(
            msr_read_scope(
                self.actor("UNKNOWN_ROLE"),
                action="list", method="GET",
            )
        )

    def test_temporary_delegation_disabled(self):
        self.assertFalse(msr_temporary_delegation_permitted())

    def test_read_does_not_grant_write_signing_or_financial_access(self):
        for role in Role.values:
            user = self.actor(role)
            with self.subTest(role=role):
                self.assertFalse(msr_read_policy_grants_write(user))
                self.assertFalse(msr_read_policy_grants_signing(user))
                self.assertFalse(
                    msr_read_policy_grants_financial_access(user)
                )