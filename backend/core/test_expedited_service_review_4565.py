from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .expedited_service_request_4565 import (
    record_expedited_service_request,
)
from .expedited_service_review_4565 import (
    REVIEW_KIND, review_expedited_service_request,
)
from .models import ProjectEvidence
from .test_installation_schedule import InstallationScheduleTests


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedReview4565Tests(TestCase):
    setUp = InstallationScheduleTests.setUp
    make_installation_eligible = InstallationScheduleTests.make_installation_eligible

    def make_request(self):
        self.make_installation_eligible()
        return record_expedited_service_request(
            actor=self.manager,
            project_id=self.project.pk,
            proposed_date=timezone.localdate() + timedelta(days=1),
            reason="Customer requests an earlier installation appointment.",
            document_reference="FICTIONAL-EXPEDITE-REQUEST-001",
        )

    def decide(self, request, actor=None):
        return review_expedited_service_request(
            actor=self.comptroller if actor is None else actor,
            request_id=request.pk,
            accept_candidate=True,
            review_reason="Independently reviewed the pending request record.",
        )

    def test_review_persists_but_never_authorizes(self):
        request = self.make_request()
        decision = self.decide(request)
        saved = ProjectEvidence.objects.get(pk=decision.pk)
        self.assertEqual(saved.kind, REVIEW_KIND)
        self.assertEqual(saved.data["status"], "CANDIDATE_ACCEPTED")
        self.assertEqual(saved.data["request_digest"], request.digest)
        self.assertEqual(saved.digest, canonical_hash(saved.data))
        for key in (
            "customer_initials_verified",
            "document_signature_verified",
            "manager_approval_verified",
            "cancellation_protections_verified",
            "expedited_authorized",
            "installation_authorized",
        ):
            self.assertIs(saved.data[key], False)

    def test_duplicate_decision_rejected(self):
        request = self.make_request()
        self.decide(request)
        before = ProjectEvidence.objects.filter(kind=REVIEW_KIND).count()
        with self.assertRaises(ValidationError):
            self.decide(request)
        self.assertEqual(
            ProjectEvidence.objects.filter(kind=REVIEW_KIND).count(), before
        )

    def test_installation_manager_cannot_review(self):
        request = self.make_request()
        with self.assertRaises(PermissionDenied):
            self.decide(request, actor=self.manager)
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=REVIEW_KIND).exists()
        )

    def test_database_rejects_request_tampering(self):
        request = self.make_request()
        changed = dict(request.data)
        changed["installation_authorized"] = True

        # Nested atomic savepoint keeps the test connection usable.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectEvidence.objects.filter(pk=request.pk).update(
                    data=changed
                )

        request.refresh_from_db()
        self.assertIs(request.data["installation_authorized"], False)
        self.assertEqual(request.digest, canonical_hash(request.data))
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=REVIEW_KIND).exists()
        )

    def test_production_mode_denies_review(self):
        # Create the fictional request while development mode is active.
        request = self.make_request()

        # Switch only the attempted review to production restrictions.
        with override_settings(ENVIRONMENT="production", DEBUG=False):
            with self.assertRaises(PermissionDenied):
                self.decide(request)

        self.assertFalse(
            ProjectEvidence.objects.filter(kind=REVIEW_KIND).exists()
        )
