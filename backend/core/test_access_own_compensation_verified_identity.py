"""Database-backed, in-memory tests for stored role eligibility."""

from django.test import TestCase

from .access_own_compensation_verified_identity import (
    verified_own_compensation_role_eligible,
    verified_identity_grants_live_access,
)
from .access_permission_catalog import has_permission
from .models import Role, User


class VerifiedOwnCompensationIdentityTests(TestCase):
    def setUp(self):
        self.person = User.objects.create_user(
            username="role_identity_test_person",
            role=Role.TECHNICIAN,
            initials="RI",
        )

    def test_active_real_user_is_role_eligible(self):
        self.assertTrue(
            verified_own_compensation_role_eligible(self.person)
        )

    def test_inactive_database_user_denied_despite_stale_actor(self):
        stored = User.objects.get(pk=self.person.pk)
        stored.is_active = False
        stored.save(update_fields=["is_active"])
        self.assertFalse(
            verified_own_compensation_role_eligible(self.person)
        )

    def test_changed_stored_role_is_rechecked(self):
        stale = User.objects.get(pk=self.person.pk)
        stored = User.objects.get(pk=self.person.pk)
        stored.role = "UNRECOGNIZED_ROLE"
        stored.save(update_fields=["role"])
        self.assertFalse(
            verified_own_compensation_role_eligible(stale)
        )

    def test_valid_role_change_uses_current_stored_role(self):
        stale = User.objects.get(pk=self.person.pk)
        stored = User.objects.get(pk=self.person.pk)
        stored.role = Role.COMPTROLLER
        stored.save(update_fields=["role"])
        self.assertTrue(
            verified_own_compensation_role_eligible(stale)
        )

    def test_missing_or_unauthenticated_identity_denied(self):
        self.assertFalse(
            verified_own_compensation_role_eligible(None)
        )
        self.assertFalse(
            verified_own_compensation_role_eligible(object())
        )
        unsaved = User(
            username="unsaved_identity",
            role=Role.CEO,
            initials="UI",
        )
        self.assertFalse(
            verified_own_compensation_role_eligible(unsaved)
        )

    def test_deleted_account_denied(self):
        stale = User.objects.get(pk=self.person.pk)
        self.person.delete()
        self.assertFalse(
            verified_own_compensation_role_eligible(stale)
        )

    def test_eligibility_never_enables_effective_permission(self):
        self.assertTrue(
            verified_own_compensation_role_eligible(self.person)
        )
        self.assertFalse(
            verified_identity_grants_live_access(self.person)
        )
        self.assertFalse(
            has_permission(self.person, "compensation.own.view")
        )