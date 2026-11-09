"""Real-database tests for inspection verification and immutability."""
from datetime import timedelta
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from . import test_installation_combined_real_evidence as fixture_module
from .equipment_physical_units import physical_units_from_snapshot
from .equipment_physical_capture_pending_service import (
    record_pending_physical_inspection,
)
from .equipment_physical_inspection_review_service import (
    review_pending_physical_inspection,
)
from .equipment_physical_inspection_verifier import (
    verify_physical_inspection_candidate,
)
from .models import AuditEvent, ProjectEvidence, Role, User


@override_settings(DEBUG=True, ENVIRONMENT="development")
class PhysicalInspectionVerificationTests(TestCase):
    def setUp(self):
        fixture = fixture_module.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        self.fixture = fixture
        self.msr = fixture.prepare()
        units = physical_units_from_snapshot(
            msr_id=str(self.msr.pk),
            snapshot=self.msr.snapshot,
        )
        self.assertTrue(units)
        self.unit_id = units[0].unit_id
        self.project_id = str(fixture.project.pk)
        self.now = timezone.now()
        self.pending = None

    def capture(self):
        self.pending = record_pending_physical_inspection(
            actor=self.fixture.installation_manager,
            project_id=self.project_id,
            msr_id=str(self.msr.pk),
            unit_id=self.unit_id,
            serial_number="GOODMAN-VERIFIER-001",
            captured_at=self.now,
            installation_starts_at=self.now + timedelta(hours=1),
            confirmed_in_person=True,
            inspection_notes="Physical equipment label independently located.",
        )
        return self.pending

    def review(self, accept=True):
        comptroller = User.objects.filter(
            role=Role.COMPTROLLER, is_active=True
        ).first()
        self.assertIsNotNone(comptroller)
        return review_pending_physical_inspection(
            actor=comptroller,
            pending_id=self.pending.pk,
            accept_candidate=accept,
            review_reason="Independent inspection candidate reviewed in detail.",
            independently_examined=accept,
        )

    def verify(self, **changes):
        values = {
            "project_id": self.project_id,
            "msr_id": str(self.msr.pk),
            "unit_id": self.unit_id,
        }
        values.update(changes)
        return verify_physical_inspection_candidate(**values)

    def assert_not_authorized(self, result):
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.installation_authorized)

    def test_accepted_review_is_only_a_verified_candidate(self):
        self.capture()
        self.review()
        before = (
            AuditEvent.objects.count(),
            ProjectEvidence.objects.count(),
        )
        result = self.verify()
        after = (
            AuditEvent.objects.count(),
            ProjectEvidence.objects.count(),
        )
        self.assertTrue(result.review_candidate_verified, result.blockers)
        self.assertEqual(before, after)
        self.assert_not_authorized(result)

    def test_capture_without_review_is_denied(self):
        self.capture()
        result = self.verify()
        self.assertFalse(result.review_candidate_verified)
        self.assertTrue(result.blockers)
        self.assert_not_authorized(result)

    def test_rejected_review_is_denied(self):
        self.capture()
        self.review(accept=False)
        result = self.verify()
        self.assertFalse(result.review_candidate_verified)
        self.assert_not_authorized(result)

    def test_wrong_msr_and_unknown_unit_are_denied(self):
        self.capture()
        self.review()
        for result in (
            self.verify(msr_id=str(uuid4())),
            self.verify(unit_id="ROW-999-UNIT-999"),
        ):
            self.assertFalse(result.review_candidate_verified)
            self.assert_not_authorized(result)

    def test_database_blocks_review_tampering_without_disabling_trigger(self):
        self.capture()
        review = self.review()

        original_digest = review.digest
        original_data = dict(review.data)
        changed_data = dict(original_data)
        changed_data["status"] = "REJECTED"

        # A nested transaction saves the test transaction after
        # the database correctly rejects immutable evidence mutation.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectEvidence.objects.filter(pk=review.pk).update(
                    data=changed_data
                )

        review.refresh_from_db()
        self.assertEqual(review.digest, original_digest)
        self.assertEqual(review.data, original_data)

        # The failed mutation must not damage valid review verification.
        result = self.verify()
        self.assertTrue(result.review_candidate_verified, result.blockers)
        self.assert_not_authorized(result)