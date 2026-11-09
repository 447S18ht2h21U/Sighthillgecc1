"""Isolated real database tests for physical-capture actor identity."""
from datetime import timedelta
from uuid import uuid4

from django.test import TestCase, override_settings
from django.utils import timezone

from . import test_installation_combined_real_evidence as fixture_module
from .equipment_physical_capture_actor_preview import (
    preview_identified_physical_capture,
)
from .equipment_physical_units import physical_units_from_snapshot
from .models import AuditEvent, ProjectEvidence, User


@override_settings(DEBUG=True, ENVIRONMENT="development")
class RealRecorderIdentityTests(TestCase):
    def setUp(self):
        fixture = fixture_module.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        self.fixture = fixture
        self.msr = fixture.prepare()
        units = physical_units_from_snapshot(
            msr_id=str(self.msr.pk), snapshot=self.msr.snapshot
        )
        self.assertTrue(units)
        self.now = timezone.now()
        self.values = {
            "project_id": str(fixture.project.pk),
            "msr_id": str(self.msr.pk),
            "unit_id": units[0].unit_id,
            "serial_number": "GOODMAN-ID-TEST",
            "recorder_id": str(fixture.installation_manager.pk),
            "captured_at": self.now,
            "installation_starts_at": self.now + timedelta(hours=1),
        }

    def assess(self, **changes):
        return preview_identified_physical_capture(
            **(self.values | changes)
        )

    def test_real_active_installation_manager_is_untrusted_candidate(self):
        before = (
            AuditEvent.objects.count(),
            ProjectEvidence.objects.count(),
        )
        result = self.assess()
        after = (
            AuditEvent.objects.count(),
            ProjectEvidence.objects.count(),
        )
        self.assertTrue(result.candidate_valid, result.blockers)
        self.assertFalse(result.physical_verification_trusted)
        self.assertFalse(result.installation_authorized)
        self.assertEqual(before, after)

    def test_real_sales_associate_cannot_record(self):
        result = self.assess(
            recorder_id=str(self.fixture.sales.pk)
        )
        self.assertFalse(result.candidate_valid)
        self.assertFalse(result.installation_authorized)

    def test_inactive_real_installation_manager_is_denied(self):
        User.objects.filter(
            pk=self.fixture.installation_manager.pk
        ).update(is_active=False)
        result = self.assess()
        self.assertFalse(result.candidate_valid)
        self.assertFalse(result.physical_verification_trusted)

    def test_unknown_recorder_is_denied(self):
        result = self.assess(recorder_id=str(uuid4()))
        self.assertFalse(result.candidate_valid)
        self.assertFalse(result.installation_authorized)