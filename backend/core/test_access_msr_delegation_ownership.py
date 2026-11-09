"""Isolated database tests for trusted MSR delegation ownership."""

from uuid import uuid4

from django.test import TestCase

from .access_msr_delegation_ownership import (
    verify_msr_delegation_project_ownership,
    verified_ownership_grants_msr_access,
)
from .models import Customer, Project, Role, User


class MSRDelegationOwnershipTests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="delegation_owner_comptroller",
            role=Role.COMPTROLLER,
        )
        self.manager = User.objects.create_user(
            username="delegation_owner_manager",
            role=Role.SALES_MANAGER,
        )
        self.source = User.objects.create_user(
            username="delegation_owner_source",
            role=Role.SALES_ASSOCIATE,
        )
        self.recipient = User.objects.create_user(
            username="delegation_owner_recipient",
            role=Role.SALES_ASSOCIATE,
        )
        self.other = User.objects.create_user(
            username="delegation_owner_other",
            role=Role.SALES_ASSOCIATE,
        )
        customer = Customer.objects.create(
            legal_name="Delegation Ownership Test Customer",
            billing_address="10 Fixture Street",
            created_by=self.comptroller,
        )
        self.project = Project.objects.create(
            code="DELEGATION-OWN-001",
            customer=customer,
            location="10 Fixture Street",
            sales_associate=self.source,
            reviewer=self.manager,
        )
        self.other_project = Project.objects.create(
            code="DELEGATION-OWN-002",
            customer=customer,
            location="12 Fixture Street",
            sales_associate=self.other,
            reviewer=self.manager,
        )

    def verify(self, **changes):
        values = {
            "manager_id": self.manager.pk,
            "recipient_id": self.recipient.pk,
            "source_associate_id": self.source.pk,
            "project_ids": (self.project.pk,),
        }
        values.update(changes)
        return verify_msr_delegation_project_ownership(**values)

    def test_owned_project_verified(self):
        self.assertEqual(self.verify(), (self.project.pk,))

    def test_other_associate_project_denied(self):
        self.assertIsNone(
            self.verify(project_ids=(self.other_project.pk,))
        )

    def test_mixed_ownership_denies_entire_request(self):
        self.assertIsNone(
            self.verify(project_ids=(
                self.project.pk, self.other_project.pk
            ))
        )

    def test_unknown_project_denied(self):
        self.assertIsNone(self.verify(project_ids=(uuid4(),)))

    def test_empty_and_duplicate_project_lists_denied(self):
        for projects in ((), (self.project.pk, self.project.pk)):
            with self.subTest(projects=projects):
                self.assertIsNone(self.verify(project_ids=projects))

    def test_non_manager_denied(self):
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

    def test_source_role_change_denied(self):
        self.source.role = Role.TECHNICIAN
        self.source.save(update_fields=["role"])
        self.assertIsNone(self.verify())

    def test_source_may_be_inactive_for_historical_coverage(self):
        self.source.is_active = False
        self.source.save(update_fields=["is_active"])
        self.assertEqual(self.verify(), (self.project.pk,))

    def test_forged_or_missing_actor_denied(self):
        self.assertIsNone(self.verify(manager_id=uuid4()))
        self.assertIsNone(self.verify(recipient_id=uuid4()))

    def test_ownership_evidence_never_grants_access(self):
        self.assertFalse(
            verified_ownership_grants_msr_access(self.verify())
        )