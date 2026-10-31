"""Isolated database-backed candidate-permission security tests."""

from django.test import TestCase

from .access_own_compensation_candidate_permission import (
    candidate_own_compensation_allowed,
    candidate_permission_is_live,
)
from .access_permission_catalog import has_permission
from .models import Role, User


CODE = "compensation.own.view"


class CandidateOwnCompensationPermissionTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="candidate_permission_3709",
            role=Role.TECHNICIAN,
            initials="CP",
        )

    def test_active_stored_role_candidate_eligible(self):
        self.assertTrue(candidate_own_compensation_allowed(self.actor, CODE))

    def test_inactive_stored_account_denied(self):
        stored = User.objects.get(pk=self.actor.pk)
        stored.is_active = False
        stored.save(update_fields=["is_active"])
        self.assertFalse(candidate_own_compensation_allowed(self.actor, CODE))

    def test_unrecognized_stored_role_denied(self):
        stored = User.objects.get(pk=self.actor.pk)
        stored.role = "INVALID_ROLE"
        stored.save(update_fields=["role"])
        self.assertFalse(candidate_own_compensation_allowed(self.actor, CODE))

    def test_other_permission_codes_and_project_scope_denied(self):
        for code in (
            None,
            "",
            "compensation.all.view",
            "financials.operations.view",
            "payroll_payments.approve",
            "users.manage",
        ):
            with self.subTest(code=code):
                self.assertFalse(
                    candidate_own_compensation_allowed(self.actor, code)
                )

        self.assertFalse(
            candidate_own_compensation_allowed(
                self.actor, CODE, project=object()
            )
        )

    def test_missing_or_deleted_actor_denied(self):
        self.assertFalse(candidate_own_compensation_allowed(None, CODE))
        stale = User.objects.get(pk=self.actor.pk)
        self.actor.delete()
        self.assertFalse(candidate_own_compensation_allowed(stale, CODE))

    def test_candidate_never_activates_live_permission(self):
        self.assertTrue(candidate_own_compensation_allowed(self.actor, CODE))
        self.assertFalse(candidate_permission_is_live())
        self.assertFalse(has_permission(self.actor, CODE))