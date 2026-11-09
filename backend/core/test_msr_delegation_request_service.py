from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from core.models import AuditEvent, AuditHead, Customer, Project, Role, User
from core.msr_delegation_models import (
    MSRDelegationRequest,
    MSRDelegationRequestProject,
)
from core.msr_delegation_request_service import (
    create_fixed_msr_delegation_request,
    request_creation_grants_live_msr_access,
    valid_request_parameters,
)


class RequestParameterTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.manager, self.recipient, self.source = [uuid4() for _ in range(3)]
        self.arguments = dict(
            manager_id=self.manager,
            recipient_id=self.recipient,
            source_associate_id=self.source,
            project_ids=[uuid4()],
            starts_at=self.now - timedelta(minutes=1),
            ends_at=self.now + timedelta(hours=1),
            reason="Temporary project coverage required",
            now=self.now,
        )

    def test_valid_parameters(self):
        self.assertTrue(valid_request_parameters(**self.arguments))

    def test_duplicate_project_denied(self):
        project = self.arguments["project_ids"][0]
        self.arguments["project_ids"] = [project, project]
        self.assertFalse(valid_request_parameters(**self.arguments))

    def test_same_person_denied(self):
        self.arguments["recipient_id"] = self.manager
        self.assertFalse(valid_request_parameters(**self.arguments))

    def test_expiration_denied(self):
        self.arguments["ends_at"] = self.now
        self.assertFalse(valid_request_parameters(**self.arguments))

    def test_empty_project_list_denied(self):
        self.arguments["project_ids"] = []
        self.assertFalse(valid_request_parameters(**self.arguments))

    def test_more_than_100_projects_denied(self):
        self.arguments["project_ids"] = [uuid4() for _ in range(101)]
        self.assertFalse(valid_request_parameters(**self.arguments))

    def test_no_live_access(self):
        self.assertFalse(request_creation_grants_live_msr_access())


class AtomicRequestDatabaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="msr_request_manager_3854",
            password="isolated-test-only",
            role=Role.SALES_MANAGER,
            initials="MGR",
        )
        cls.recipient = User.objects.create_user(
            username="msr_request_recipient_3854",
            password="isolated-test-only",
            role=Role.SALES_ASSOCIATE,
            initials="REC",
        )
        cls.source = User.objects.create_user(
            username="msr_request_source_3854",
            password="isolated-test-only",
            role=Role.SALES_ASSOCIATE,
            initials="SRC",
        )
        cls.customer = Customer.objects.create(
            created_by=cls.manager,
            legal_name="Temporary MSR Test Customer",
            billing_address="Test Address",
            phone="5550000100",
            email="msr-test@example.invalid",
        )
        cls.project = Project.objects.create(
            code="MSR-REQUEST-3854",
            customer=cls.customer,
            location="Test Project",
            sales_associate=cls.source,
            reviewer=cls.manager,
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)
        now = timezone.now()
        self.arguments = dict(
            manager_id=self.manager.pk,
            recipient_id=self.recipient.pk,
            source_associate_id=self.source.pk,
            project_ids=[self.project.pk],
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(hours=1),
            reason="Temporary project coverage required",
        )

    def test_success_creates_snapshot_and_audit(self):
        request = create_fixed_msr_delegation_request(**self.arguments)
        self.assertEqual(MSRDelegationRequest.objects.count(), 1)
        self.assertEqual(MSRDelegationRequestProject.objects.count(), 1)
        scope = MSRDelegationRequestProject.objects.get(request=request)
        self.assertEqual(scope.owner_revision, self.project.ownership_revision)
        self.assertEqual(AuditEvent.objects.filter(
            action="msr.delegation.requested"
        ).count(), 1)

    def test_audit_failure_rolls_back_all_evidence(self):
        with patch(
            "core.msr_delegation_request_service.audit",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Simulated audit"):
                create_fixed_msr_delegation_request(**self.arguments)
        self.assertFalse(MSRDelegationRequest.objects.exists())
        self.assertFalse(MSRDelegationRequestProject.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(
            action="msr.delegation.requested"
        ).exists())

    def test_reassigned_project_denied_without_evidence(self):
        self.project.sales_associate = self.recipient
        self.project.save(update_fields=["sales_associate"])
        with self.assertRaises(PermissionDenied):
            create_fixed_msr_delegation_request(**self.arguments)
        self.assertFalse(MSRDelegationRequest.objects.exists())

    def test_inactive_manager_denied(self):
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            create_fixed_msr_delegation_request(**self.arguments)
        self.assertFalse(MSRDelegationRequest.objects.exists())

    def test_invalid_scope_denied_before_write(self):
        self.arguments["project_ids"] = [uuid4()]
        with self.assertRaises(PermissionDenied):
            create_fixed_msr_delegation_request(**self.arguments)
        self.assertFalse(MSRDelegationRequest.objects.exists())