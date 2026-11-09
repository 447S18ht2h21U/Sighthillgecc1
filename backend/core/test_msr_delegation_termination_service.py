"""Disposable-database tests for MSR delegation termination."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from core.models import AuditEvent, AuditHead, Customer, Project, Role, User
from core.msr_delegation_models import MSRDelegationTermination
from core.msr_delegation_request_service import (
    create_fixed_msr_delegation_request,
)
from core.msr_delegation_approval_service import approve_fixed_msr_delegation
from core.msr_delegation_termination_service import (
    terminate_fixed_msr_delegation,
    termination_service_grants_live_msr_access,
)


class TerminationTransactionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def person(name, role):
            return User.objects.create_user(
                username="msr3856" + name,
                password="isolated-test-only",
                role=role,
                initials=name[:3].upper(),
            )

        cls.manager = person("manager", Role.SALES_MANAGER)
        cls.source = person("source", Role.SALES_ASSOCIATE)
        cls.recipient = person("recipient", Role.SALES_ASSOCIATE)
        cls.ceo = person("ceo", Role.CEO)
        cls.comptroller = person("comptroller", Role.COMPTROLLER)
        cls.customer = Customer.objects.create(
            created_by=cls.manager,
            legal_name="MSR Termination Test Customer",
            billing_address="Test Address",
            phone="5550000102",
            email="msr-termination@example.invalid",
        )
        cls.project = Project.objects.create(
            code="MSR-TERM-3856",
            customer=cls.customer,
            location="Temporary Test Site",
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
            project_ids=[self.project.pk],
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(hours=1),
            reason="Fixed project backup coverage requirement",
        )
        self.decision = approve_fixed_msr_delegation(
            request_id=request.pk,
            approver_id=self.comptroller.pk,
            reason="Independent approval for temporary coverage",
        )

    def end(self, actor=None, kind="ADMINISTRATIVE_REVOCATION"):
        return terminate_fixed_msr_delegation(
            decision_id=self.decision.pk,
            actor_id=self.ceo.pk if actor is None else actor.pk,
            kind=kind,
            reason="Temporary project coverage is no longer required",
        )

    def test_ceo_revocation_and_audit(self):
        event = self.end()
        self.assertEqual(event.kind, "ADMINISTRATIVE_REVOCATION")
        self.assertEqual(MSRDelegationTermination.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(
            action="msr.delegation.terminated"
        ).count(), 1)

    def test_comptroller_revocation(self):
        event = self.end(self.comptroller)
        self.assertEqual(event.terminated_by_id, self.comptroller.pk)

    def test_recipient_voluntary_surrender(self):
        event = self.end(self.recipient, "VOLUNTARY_SURRENDER")
        self.assertEqual(event.kind, "VOLUNTARY_SURRENDER")

    def test_manager_cannot_revoke(self):
        with self.assertRaises(PermissionDenied):
            self.end(self.manager)
        self.assertFalse(MSRDelegationTermination.objects.exists())

    def test_source_cannot_surrender(self):
        with self.assertRaises(PermissionDenied):
            self.end(self.source, "VOLUNTARY_SURRENDER")
        self.assertFalse(MSRDelegationTermination.objects.exists())

    def test_recipient_cannot_administratively_revoke(self):
        with self.assertRaises(PermissionDenied):
            self.end(self.recipient)
        self.assertFalse(MSRDelegationTermination.objects.exists())

    def test_duplicate_termination_denied(self):
        self.end()
        with self.assertRaises(PermissionDenied):
            self.end(self.comptroller)
        self.assertEqual(MSRDelegationTermination.objects.count(), 1)

    def test_audit_failure_rolls_back_termination(self):
        with patch(
            "core.msr_delegation_termination_service.audit",
            side_effect=RuntimeError("Simulated termination audit failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Simulated termination"):
                self.end()
        self.assertFalse(MSRDelegationTermination.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(
            action="msr.delegation.terminated"
        ).exists())

    def test_inactive_executive_denied(self):
        User.objects.filter(pk=self.ceo.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.end()
        self.assertFalse(MSRDelegationTermination.objects.exists())

    def test_invalid_reason_denied(self):
        with self.assertRaises(PermissionDenied):
            terminate_fixed_msr_delegation(
                decision_id=self.decision.pk,
                actor_id=self.ceo.pk,
                kind="ADMINISTRATIVE_REVOCATION",
                reason="short",
            )

    def test_automatic_expiration_cannot_be_forged(self):
        with self.assertRaises(PermissionDenied):
            self.end(self.ceo, "AUTOMATIC_EXPIRATION")

    def test_never_grants_live_access(self):
        self.assertFalse(termination_service_grants_live_msr_access())