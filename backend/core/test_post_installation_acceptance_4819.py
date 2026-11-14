"""Disposable-database post-installation inspection acceptance tests."""
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import test_installation_combined_real_evidence as fixture_module
from .models import (
    InstallationSchedule, ProjectEvidence, Role, User,
)
from .post_installation_acceptance_4819 import (
    INSPECTION_KIND, REVIEW_KIND,
    record_post_installation_inspection,
    review_post_installation_inspection,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class PostInstallationAcceptance4819(TestCase):
    def setUp(self):
        fixture = fixture_module.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        self.fixture = fixture
        self.msr = fixture.prepare()
        self.project = fixture.project
        self.inspector = fixture.installation_manager
        self.reviewer = User.objects.filter(
            role=Role.COMPTROLLER, is_active=True
        ).first()
        self.assertIsNotNone(self.reviewer)

        self.schedule = InstallationSchedule.objects.create(
            project=self.project,
            scheduled_date=timezone.localdate(),
            installation_manager=self.inspector,
            scheduled_by=self.inspector,
            status=InstallationSchedule.Status.COMPLETED,
            completed_at=timezone.now(),
        )

    def capture(self, **changes):
        args = {
            "actor": self.inspector,
            "project_id": self.project.pk,
            "inspection_passed": True,
            "notes": "Post-installation workmanship and system checked.",
        }
        return record_post_installation_inspection(**(args | changes))

    def review(self, inspection, **changes):
        args = {
            "actor": self.reviewer,
            "inspection_id": inspection.pk,
            "accept": True,
            "reason": "Independent evidence review supports candidate acceptance.",
            "independently_examined": True,
        }
        return review_post_installation_inspection(**(args | changes))

    def test_valid_independent_review_remains_non_authorizing(self):
        inspection = self.capture()
        review = self.review(inspection)
        self.assertEqual(inspection.kind, INSPECTION_KIND)
        self.assertEqual(review.kind, REVIEW_KIND)
        self.assertEqual(review.data["status"], "CANDIDATE_ACCEPTED")
        self.assertFalse(review.data["trusted_installation_evidence"])
        self.assertFalse(review.data["final_receipt_issuance_authorized"])

    def test_duplicate_inspection_and_review_rejected(self):
        inspection = self.capture()
        self.review(inspection)
        with self.assertRaises(ValidationError):
            self.capture()
        with self.assertRaises(ValidationError):
            self.review(inspection)
        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr,
                kind__in=(INSPECTION_KIND, REVIEW_KIND),
            ).count(), 2
        )

    def test_rejected_inspection_cannot_be_accepted(self):
        inspection = self.capture(inspection_passed=False)
        with self.assertRaises(ValidationError):
            self.review(inspection)
        rejection = self.review(
            inspection, accept=False, independently_examined=False
        )
        self.assertEqual(rejection.data["status"], "REJECTED")

    def test_other_role_cannot_record_inspection(self):
        with self.assertRaises(PermissionDenied):
            self.capture(actor=self.reviewer)
        self.assertFalse(ProjectEvidence.objects.filter(
            msr=self.msr, kind=INSPECTION_KIND
        ).exists())

    def test_missing_completed_schedule_denied(self):
        self.schedule.delete()
        with self.assertRaises(ValidationError):
            self.capture()

    def test_self_review_denied(self):
        inspection = self.capture()
        with self.assertRaises(PermissionDenied):
            self.review(inspection, actor=self.inspector)
