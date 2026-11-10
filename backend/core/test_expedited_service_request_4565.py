from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from .documents import canonical_hash
from .expedited_service_request_4565 import (
    KIND, record_expedited_service_request,
)
from .models import ProjectEvidence
from .test_installation_schedule import InstallationScheduleTests


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedServiceRequest4565Tests(TestCase):
    setUp = InstallationScheduleTests.setUp
    make_installation_eligible = InstallationScheduleTests.make_installation_eligible

    def record(self, actor=None):
        return record_expedited_service_request(
            actor=self.manager if actor is None else actor,
            project_id=self.project.pk,
            proposed_date=timezone.localdate() + timedelta(days=1),
            reason="Customer requests an earlier installation appointment.",
            document_reference="DOC-EXPEDITED-TEST-001",
        )

    def test_route_and_anonymous_denial(self):
        url = reverse("installation-schedules-request-expedited")
        self.assertEqual(
            resolve(url).func.actions["post"],
            "request_expedited_service",
        )
        response = APIClient().post(
            url,
            {
                "project": str(self.project.pk),
                "proposed_date": (
                    timezone.localdate() + timedelta(days=1)
                ).isoformat(),
                "reason": "Customer requests earlier installation.",
                "document_reference": "DOC-EXPEDITED-TEST-001",
            },
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(ProjectEvidence.objects.filter(kind=KIND).exists())

    def test_request_persists_untrusted_and_immutable(self):
        self.make_installation_eligible()
        evidence = self.record()
        saved = ProjectEvidence.objects.get(pk=evidence.pk)

        self.assertEqual(saved.kind, KIND)
        self.assertEqual(saved.msr_id, self.project.current_approved_id)
        self.assertEqual(saved.digest, canonical_hash(saved.data))
        self.assertEqual(
            saved.data["status"], "PENDING_INDEPENDENT_VERIFICATION"
        )
        for field in (
            "customer_initials_verified",
            "document_signature_verified",
            "manager_approval_verified",
            "cancellation_protections_verified",
            "expedited_authorized",
            "installation_authorized",
        ):
            self.assertIs(saved.data[field], False)

        with self.assertRaises(Exception):
            saved.save()

    def test_duplicate_request_rejected(self):
        self.make_installation_eligible()
        self.record()
        before = ProjectEvidence.objects.filter(kind=KIND).count()
        with self.assertRaises(ValidationError):
            self.record()
        self.assertEqual(
            ProjectEvidence.objects.filter(kind=KIND).count(), before
        )

    def test_sales_associate_denied(self):
        self.make_installation_eligible()
        with self.assertRaises(PermissionDenied):
            self.record(actor=self.sales)
        self.assertFalse(ProjectEvidence.objects.filter(kind=KIND).exists())

    def test_unapproved_msr_denied(self):
        with self.assertRaises(ValidationError):
            self.record()
        self.assertFalse(ProjectEvidence.objects.filter(kind=KIND).exists())

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_restriction_remains_enforced(self):
        self.make_installation_eligible()
        with self.assertRaises(PermissionDenied):
            self.record()
        self.assertFalse(ProjectEvidence.objects.filter(kind=KIND).exists())