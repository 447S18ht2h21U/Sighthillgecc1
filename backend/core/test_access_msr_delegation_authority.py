"""Isolated database tests for MSR delegation decision authority."""

from uuid import uuid4

from django.test import TestCase

from .access_msr_delegation_authority import (
    trusted_authority_check_grants_access,
    verify_msr_delegation_approval_authority,
)
from .models import Role, User


class MSRDelegationAuthorityTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="msr_authority_manager",
            role=Role.SALES_MANAGER,
        )
        self.recipient = User.objects.create_user(
            username="msr_authority_recipient",
            role=Role.SALES_ASSOCIATE,
        )
        self.source = User.objects.create_user(
            username="msr_authority_source",
            role=Role.SALES_ASSOCIATE,
        )
        self.ceo = User.objects.create_user(
            username="msr_authority_ceo",
            role=Role.CEO,
        )
        self.comptroller = User.objects.create_user(
            username="msr_authority_comptroller",
            role=Role.COMPTROLLER,
        )
        self.technician = User.objects.create_user(
            username="msr_authority_technician",
            role=Role.TECHNICIAN,
        )

    def verify(self, **changes):
        values = {
            "manager_id": self.manager.pk,
            "recipient_id": self.recipient.pk,
            "source_associate_id": self.source.pk,
            "approver_id": self.ceo.pk,
        }
        values.update(changes)
        return verify_msr_delegation_approval_authority(**values)

    def test_ceo_independent_approval_identity_verified(self):
        self.assertEqual(
            self.verify(),
            (
                self.manager.pk,
                self.recipient.pk,
                self.source.pk,
                self.ceo.pk,
            ),
        )

    def test_comptroller_approval_identity_verified(self):
        self.assertEqual(
            self.verify(approver_id=self.comptroller.pk)[3],
            self.comptroller.pk,
        )

    def test_manager_cannot_approve_own_request(self):
        self.assertIsNone(
            self.verify(approver_id=self.manager.pk)
        )

    def test_recipient_cannot_approve(self):
        self.assertIsNone(
            self.verify(approver_id=self.recipient.pk)
        )

    def test_source_cannot_approve(self):
        self.assertIsNone(
            self.verify(approver_id=self.source.pk)
        )

    def test_technician_cannot_approve(self):
        self.assertIsNone(
            self.verify(approver_id=self.technician.pk)
        )

    def test_non_manager_cannot_request(self):
        self.assertIsNone(
            self.verify(manager_id=self.comptroller.pk)
        )

    def test_inactive_manager_denied(self):
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        self.assertIsNone(self.verify())

    def test_inactive_recipient_denied(self):
        self.recipient.is_active = False
        self.recipient.save(update_fields=["is_active"])
        self.assertIsNone(self.verify())

    def test_inactive_approver_denied(self):
        self.ceo.is_active = False
        self.ceo.save(update_fields=["is_active"])
        self.assertIsNone(self.verify())

    def test_source_role_change_denied(self):
        self.source.role = Role.TECHNICIAN
        self.source.save(update_fields=["role"])
        self.assertIsNone(self.verify())

    def test_inactive_source_supported_for_coverage(self):
        self.source.is_active = False
        self.source.save(update_fields=["is_active"])
        self.assertEqual(self.verify()[2], self.source.pk)

    def test_unknown_identity_denied(self):
        self.assertIsNone(
            self.verify(approver_id=uuid4())
        )

    def test_identity_check_does_not_grant_access(self):
        self.assertFalse(
            trusted_authority_check_grants_access(self.verify())
        )