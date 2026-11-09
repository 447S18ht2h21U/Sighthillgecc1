"""Disposable-database eligibility tests covering an entire lifecycle."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.models import AuditHead, Customer, Project, Role, User
from core.msr_delegation_request_service import (
    create_fixed_msr_delegation_request,
)
from core.msr_delegation_approval_service import approve_fixed_msr_delegation
from core.msr_delegation_termination_service import (
    terminate_fixed_msr_delegation,
)
from core.msr_delegation_reassignment_service import (
    reassign_project_with_msr_invalidation,
)
from core.msr_delegation_eligibility_service import (
    eligible_fixed_project_delegation,
    eligibility_check_grants_live_msr_access,
)


class DelegationEligibilityLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def person(name, role):
            return User.objects.create_user(
                username="msr3859" + name,
                password="isolated-test-only",
                role=role,
                initials=name[:3].upper(),
            )

        cls.manager = person("manager", Role.SALES_MANAGER)
        cls.source = person("source", Role.SALES_ASSOCIATE)
        cls.recipient = person("recipient", Role.SALES_ASSOCIATE)
        cls.new_owner = person("newowner", Role.SALES_ASSOCIATE)
        cls.comptroller = person("comptroller", Role.COMPTROLLER)
        cls.ceo = person("ceo", Role.CEO)

        cls.customer = Customer.objects.create(
            created_by=cls.manager,
            legal_name="MSR Eligibility Isolated Customer",
            billing_address="Test Address",
            phone="5550000104",
            email="msr-eligibility@example.invalid",
        )
        cls.project_a = Project.objects.create(
            code="MSR-ELIG-A-3859",
            customer=cls.customer,
            location="Temporary Site A",
            sales_associate=cls.source,
            reviewer=cls.manager,
        )
        cls.project_b = Project.objects.create(
            code="MSR-ELIG-B-3859",
            customer=cls.customer,
            location="Temporary Site B",
            sales_associate=cls.source,
            reviewer=cls.manager,
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)
        self.now = timezone.now()
        self.request = create_fixed_msr_delegation_request(
            manager_id=self.manager.pk,
            recipient_id=self.recipient.pk,
            source_associate_id=self.source.pk,
            project_ids=[self.project_a.pk, self.project_b.pk],
            starts_at=self.now - timedelta(minutes=1),
            ends_at=self.now + timedelta(hours=1),
            reason="Fixed project coverage required temporarily",
        )

    def eligible(self, project=None, now=None):
        return eligible_fixed_project_delegation(
            recipient_id=self.recipient.pk,
            project_id=(
                self.project_a.pk if project is None else project.pk
            ),
            now=self.now if now is None else now,
        )

    def approve(self):
        return approve_fixed_msr_delegation(
            request_id=self.request.pk,
            approver_id=self.comptroller.pk,
            reason="Independent approval of fixed project coverage",
        )

    def reassign(self, owner):
        return reassign_project_with_msr_invalidation(
            project_id=self.project_a.pk,
            new_owner_id=owner.pk,
            actor_id=self.comptroller.pk,
            reason="Authorized change of project ownership",
        )

    def test_pending_request_is_not_eligible(self):
        self.assertFalse(self.eligible())

    def test_approval_makes_scope_eligible_for_inspection(self):
        self.approve()
        self.assertTrue(self.eligible())
        self.assertTrue(self.eligible(self.project_b))

    def test_other_project_remains_denied(self):
        self.approve()
        self.assertFalse(eligible_fixed_project_delegation(
            recipient_id=self.recipient.pk,
            project_id=self.customer.pk,
            now=self.now,
        ))

    def test_expired_scope_denied(self):
        self.approve()
        self.assertFalse(self.eligible(
            now=self.now + timedelta(days=2)
        ))

    def test_revocation_disables_all_scopes(self):
        decision = self.approve()
        terminate_fixed_msr_delegation(
            decision_id=decision.pk,
            actor_id=self.ceo.pk,
            kind="ADMINISTRATIVE_REVOCATION",
            reason="Temporary delegation access administratively revoked",
        )
        self.assertFalse(self.eligible())
        self.assertFalse(self.eligible(self.project_b))

    def test_reassignment_only_disables_changed_project(self):
        self.approve()
        self.reassign(self.new_owner)
        self.assertFalse(self.eligible())
        self.assertTrue(self.eligible(self.project_b))

    def test_ownership_return_does_not_reactivate(self):
        self.approve()
        self.reassign(self.new_owner)
        self.reassign(self.source)
        self.assertFalse(self.eligible())
        self.assertTrue(self.eligible(self.project_b))

    def test_inactive_recipient_denied(self):
        self.approve()
        User.objects.filter(pk=self.recipient.pk).update(is_active=False)
        self.assertFalse(self.eligible())

    def test_operational_access_remains_disabled(self):
        self.approve()
        self.assertFalse(eligibility_check_grants_live_msr_access())