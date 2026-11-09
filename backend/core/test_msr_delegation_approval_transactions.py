"""Database-backed approval tests. All records use the disposable test DB."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from core.models import AuditEvent, AuditHead, Customer, Project, Role, User
from core.msr_delegation_models import MSRDelegationDecision
from core.msr_delegation_request_service import create_fixed_msr_delegation_request
from core.msr_delegation_approval_service import approve_fixed_msr_delegation


class AtomicApprovalTransactionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def person(username, role, initials):
            return User.objects.create_user(
                username=username,
                password="isolated-test-only",
                role=role,
                initials=initials,
            )

        cls.manager = person("msr3855manager", Role.SALES_MANAGER, "MGR")
        cls.recipient = person("msr3855recipient", Role.SALES_ASSOCIATE, "REC")
        cls.source = person("msr3855source", Role.SALES_ASSOCIATE, "SRC")
        cls.comptroller = person("msr3855comp", Role.COMPTROLLER, "CMP")
        cls.ceo = person("msr3855ceo", Role.CEO, "CEO")
        cls.customer = Customer.objects.create(
            created_by=cls.manager,
            legal_name="MSR Approval Transaction Test",
            billing_address="Test Address",
            phone="5550000101",
            email="msr-approval@example.invalid",
        )
        cls.project = Project.objects.create(
            code="MSR-APPROVAL-3855",
            customer=cls.customer,
            location="Isolated Test Project",
            sales_associate=cls.source,
            reviewer=cls.manager,
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)
        now = timezone.now()
        self.request = create_fixed_msr_delegation_request(
            manager_id=self.manager.pk,
            recipient_id=self.recipient.pk,
            source_associate_id=self.source.pk,
            project_ids=[self.project.pk],
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(hours=1),
            reason="Temporary coverage of a fixed sales project",
        )

    def approve(self, approver=None):
        return approve_fixed_msr_delegation(
            request_id=self.request.pk,
            approver_id=(
                self.comptroller.pk if approver is None else approver.pk
            ),
            reason="Independent authorization for temporary project coverage",
        )

    def test_comptroller_approval_and_audit(self):
        decision = self.approve()
        self.assertEqual(decision.result, "APPROVED")
        self.assertEqual(decision.decided_by_id, self.comptroller.pk)
        self.assertEqual(MSRDelegationDecision.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(
            action="msr.delegation.approved"
        ).count(), 1)

    def test_ceo_can_approve_independently(self):
        decision = self.approve(self.ceo)
        self.assertEqual(decision.decided_by_id, self.ceo.pk)

    def test_manager_cannot_approve_own_request(self):
        with self.assertRaises(PermissionDenied):
            self.approve(self.manager)
        self.assertFalse(MSRDelegationDecision.objects.exists())

    def test_recipient_cannot_approve(self):
        with self.assertRaises(PermissionDenied):
            self.approve(self.recipient)
        self.assertFalse(MSRDelegationDecision.objects.exists())

    def test_second_approval_is_rejected(self):
        self.approve()
        with self.assertRaises(PermissionDenied):
            self.approve(self.ceo)
        self.assertEqual(MSRDelegationDecision.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(
            action="msr.delegation.approved"
        ).count(), 1)

    def test_failed_audit_rolls_back_decision(self):
        with patch(
            "core.msr_delegation_approval_service.audit",
            side_effect=RuntimeError("Simulated approval audit failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Simulated approval"):
                self.approve()
        self.assertFalse(MSRDelegationDecision.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(
            action="msr.delegation.approved"
        ).exists())

    def test_changed_ownership_revision_rejects_approval(self):
        Project.objects.filter(pk=self.project.pk).update(
            ownership_revision=1
        )
        with self.assertRaises(PermissionDenied):
            self.approve()
        self.assertFalse(MSRDelegationDecision.objects.exists())

    def test_changed_owner_rejects_approval(self):
        Project.objects.filter(pk=self.project.pk).update(
            sales_associate=self.recipient,
            ownership_revision=1,
        )
        with self.assertRaises(PermissionDenied):
            self.approve()
        self.assertFalse(MSRDelegationDecision.objects.exists())

    def test_inactive_approver_rejected(self):
        User.objects.filter(pk=self.comptroller.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.approve()
        self.assertFalse(MSRDelegationDecision.objects.exists())

    def test_invalid_reason_rejected(self):
        with self.assertRaises(PermissionDenied):
            approve_fixed_msr_delegation(
                request_id=self.request.pk,
                approver_id=self.comptroller.pk,
                reason="short",
            )
        self.assertFalse(MSRDelegationDecision.objects.exists())