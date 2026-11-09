"""Database-backed ownership revision and partial-scope invalidation."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from core.models import AuditEvent, AuditHead, Customer, Project, Role, User
from core.msr_delegation_models import MSRDelegationProjectInvalidation
from core.msr_delegation_request_service import (
    create_fixed_msr_delegation_request,
)
from core.msr_delegation_approval_service import approve_fixed_msr_delegation
from core.msr_delegation_reassignment_service import (
    reassign_project_with_msr_invalidation,
    reassignment_grants_live_msr_access,
)


class ReassignmentInvalidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def person(name, role):
            return User.objects.create_user(
                username="msr3857" + name,
                password="isolated-test-only",
                role=role,
                initials=name[:3].upper(),
            )
        cls.manager = person("manager", Role.SALES_MANAGER)
        cls.source = person("source", Role.SALES_ASSOCIATE)
        cls.recipient = person("recipient", Role.SALES_ASSOCIATE)
        cls.new_owner = person("newowner", Role.SALES_ASSOCIATE)
        cls.comptroller = person("comptroller", Role.COMPTROLLER)
        cls.customer = Customer.objects.create(
            created_by=cls.manager,
            legal_name="MSR Reassignment Isolated Customer",
            billing_address="Test Address",
            phone="5550000103",
            email="msr-reassignment@example.invalid",
        )
        cls.project_a = Project.objects.create(
            code="MSR-REASSIGN-A-3857",
            customer=cls.customer,
            location="Temporary Site A",
            sales_associate=cls.source,
            reviewer=cls.manager,
        )
        cls.project_b = Project.objects.create(
            code="MSR-REASSIGN-B-3857",
            customer=cls.customer,
            location="Temporary Site B",
            sales_associate=cls.source,
            reviewer=cls.manager,
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)
        now = timezone.now()
        request = create_fixed_msr_delegation_request(
            manager_id=self.manager.pk,
            recipient_id=self.recipient.pk,
            source_associate_id=self.source.pk,
            project_ids=[self.project_a.pk, self.project_b.pk],
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(hours=1),
            reason="Two-project temporary coverage requested",
        )
        self.decision = approve_fixed_msr_delegation(
            request_id=request.pk,
            approver_id=self.comptroller.pk,
            reason="Independent temporary access approval",
        )

    def change(self, project=None, owner=None, actor=None):
        return reassign_project_with_msr_invalidation(
            project_id=self.project_a.pk if project is None else project.pk,
            new_owner_id=self.new_owner.pk if owner is None else owner.pk,
            actor_id=self.comptroller.pk if actor is None else actor.pk,
            reason="Approved change of sales project ownership",
        )

    def test_one_project_invalidated_other_preserved(self):
        result = self.change()
        self.assertEqual(result.ownership_revision, 1)
        invalidated = list(
            MSRDelegationProjectInvalidation.objects.values_list(
                "scope__project_id", flat=True
            )
        )
        self.assertEqual(invalidated, [self.project_a.pk])
        self.project_b.refresh_from_db()
        self.assertEqual(self.project_b.ownership_revision, 0)
        self.assertEqual(self.project_b.sales_associate_id, self.source.pk)

    def test_ownership_change_audited(self):
        self.change()
        self.assertEqual(AuditEvent.objects.filter(
            action="msr.project.reassigned"
        ).count(), 1)

    def test_owner_return_cannot_reactivate_scope(self):
        self.change()
        self.change(owner=self.source)
        self.project_a.refresh_from_db()
        self.assertEqual(self.project_a.ownership_revision, 2)
        self.assertEqual(
            MSRDelegationProjectInvalidation.objects.count(), 1
        )
        self.assertEqual(
            MSRDelegationProjectInvalidation.objects.get().scope.owner_revision,
            0,
        )

    def test_manager_cannot_reassign(self):
        with self.assertRaises(PermissionDenied):
            self.change(actor=self.manager)
        self.assertFalse(MSRDelegationProjectInvalidation.objects.exists())

    def test_same_owner_change_denied(self):
        with self.assertRaises(PermissionDenied):
            self.change(owner=self.source)
        self.assertFalse(MSRDelegationProjectInvalidation.objects.exists())

    def test_inactive_new_owner_denied(self):
        User.objects.filter(pk=self.new_owner.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.change()
        self.assertFalse(MSRDelegationProjectInvalidation.objects.exists())

    def test_audit_failure_rolls_back_all_changes(self):
        with patch(
            "core.msr_delegation_reassignment_service.audit",
            side_effect=RuntimeError("Simulated reassignment audit failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Simulated reassignment"):
                self.change()
        self.project_a.refresh_from_db()
        self.assertEqual(self.project_a.sales_associate_id, self.source.pk)
        self.assertEqual(self.project_a.ownership_revision, 0)
        self.assertFalse(MSRDelegationProjectInvalidation.objects.exists())

    def test_no_live_permissions(self):
        self.assertFalse(reassignment_grants_live_msr_access())