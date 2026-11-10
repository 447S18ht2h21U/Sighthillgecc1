from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from .documents import canonical_hash
from .expedited_service_request_4565 import record_expedited_service_request
from .expedited_service_review_4565 import review_expedited_service_request
from .expedited_manager_decision_4565 import (
    DECISION_KIND, decide_expedited_service_request,
)
from .models import ProjectEvidence
from .test_installation_schedule import InstallationScheduleTests


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedManagerDecision4565Tests(TestCase):
    setUp = InstallationScheduleTests.setUp
    make_installation_eligible = InstallationScheduleTests.make_installation_eligible

    def make_review(self, accept=True):
        self.make_installation_eligible()
        request = record_expedited_service_request(
            actor=self.manager,
            project_id=self.project.pk,
            proposed_date=timezone.localdate() + timedelta(days=1),
            reason="Customer requested an accelerated installation appointment.",
            document_reference="FICTIONAL-EXPEDITE-REQUEST-001",
        )
        return review_expedited_service_request(
            actor=self.comptroller,
            request_id=request.pk,
            accept_candidate=accept,
            review_reason="Independently examined the pending fictional request.",
        )

    def decide(self, review, actor=None):
        return decide_expedited_service_request(
            actor=self.manager if actor is None else actor,
            review_id=review.pk,
            approve=True,
            decision_reason="Manager recorded approval pending customer evidence.",
        )

    def test_approved_candidate_does_not_authorize(self):
        review = self.make_review()
        decision = self.decide(review)
        stored = ProjectEvidence.objects.get(pk=decision.pk)
        self.assertEqual(stored.kind, DECISION_KIND)
        self.assertEqual(stored.digest, canonical_hash(stored.data))
        self.assertEqual(
            stored.data["status"],
            "MANAGER_APPROVED_PENDING_CUSTOMER_EVIDENCE",
        )
        self.assertEqual(stored.data["review_digest"], review.digest)
        for key in (
            "customer_initials_verified",
            "document_signature_verified",
            "cancellation_protections_verified",
            "expedited_authorized",
            "installation_authorized",
        ):
            self.assertIs(stored.data[key], False)

    def test_duplicate_manager_decision_denied(self):
        review = self.make_review()
        self.decide(review)
        with self.assertRaises(ValidationError):
            self.decide(review)
        self.assertEqual(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).count(), 1
        )

    def test_comptroller_cannot_make_manager_decision(self):
        review = self.make_review()
        with self.assertRaises(PermissionDenied):
            self.decide(review, actor=self.comptroller)
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).exists()
        )

    def test_rejected_review_cannot_be_approved(self):
        review = self.make_review(accept=False)
        with self.assertRaises(ValidationError):
            self.decide(review)

    def test_anonymous_api_rejected(self):
        url = reverse("installation-schedules-decide-expedited")
        self.assertEqual(
            resolve(url).func.actions["post"], "decide_expedited_service"
        )
        response = APIClient().post(url, {
            "review_id": "11111111-1111-4111-8111-111111111111",
            "approve": True,
            "decision_reason": "Fictional manager decision for verification.",
        }, format="json")
        self.assertIn(response.status_code, (401, 403))

    def test_production_mode_rejected(self):
        review = self.make_review()
        with override_settings(ENVIRONMENT="production", DEBUG=False):
            with self.assertRaises(PermissionDenied):
                self.decide(review)
