"""Focused isolated tests for recorded equipment readiness preview."""
from datetime import timedelta
from django.test import override_settings
from django.utils import timezone

from .equipment_recorded_readiness_preview import preview_recorded_equipment
from .equipment_serial_capture_service import capture_synthetic_serial
from .test_equipment_serial_exception_service import (
    SerialExceptionRequestServiceTests,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class RecordedEquipmentPreviewTests(SerialExceptionRequestServiceTests):
    def preview_saved(self, msr):
        return preview_recorded_equipment(
            project_id=self.project.pk,
            msr_id=msr.pk,
            installation_starts_at=timezone.now() + timedelta(hours=1),
        )

    def save_serial(self, msr, number, serial):
        return capture_synthetic_serial(
            actor=self.installation_manager,
            project_id=self.project.pk,
            msr_id=msr.pk,
            unit_id=f"ROW-001-UNIT-{number:03d}",
            serial_number=serial,
        )

    def test_two_saved_serials_are_only_readiness_candidates(self):
        msr = self.prepare()
        self.save_serial(msr, 1, "GOODMAN-A")
        self.save_serial(msr, 2, "GOODMAN-B")
        result = self.preview_saved(msr)
        self.assertTrue(result.candidate_complete, result.blockers)
        self.assertEqual(len(result.serial_units), 2)
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.installation_authorized)

    def test_saved_serial_and_comptroller_approval_match(self):
        msr = self.prepare()
        self.save_serial(msr, 2, "GOODMAN-B")
        request = self.request(msr)
        self.decide(request)
        result = self.preview_saved(msr)
        self.assertTrue(result.candidate_complete, result.blockers)
        self.assertEqual(
            result.exception_candidate_units, ("ROW-001-UNIT-001",)
        )
        self.assertFalse(result.installation_authorized)

    def test_missing_unit_blocks(self):
        msr = self.prepare()
        self.save_serial(msr, 1, "GOODMAN-A")
        result = self.preview_saved(msr)
        self.assertFalse(result.candidate_complete)

    def test_revoked_exception_blocks(self):
        msr = self.prepare()
        self.save_serial(msr, 2, "GOODMAN-B")
        request = self.request(msr)
        decision = self.decide(request)
        self.revoke(decision)
        result = self.preview_saved(msr)
        self.assertFalse(result.candidate_complete)

    def test_serial_and_exception_on_same_unit_block(self):
        msr = self.prepare()
        self.save_serial(msr, 1, "GOODMAN-A")
        self.save_serial(msr, 2, "GOODMAN-B")
        request = self.request(msr)
        self.decide(request)
        result = self.preview_saved(msr)
        self.assertFalse(result.candidate_complete)

    def test_duplicate_saved_capture_blocks(self):
        from .equipment_serial_capture_service import SERIAL_KIND
        from .models import ProjectEvidence
        msr = self.prepare()
        first = self.save_serial(msr, 1, "GOODMAN-A")
        self.save_serial(msr, 2, "GOODMAN-B")
        ProjectEvidence.objects.create(
            msr=msr,
            kind=SERIAL_KIND,
            created_by=first.created_by,
            data=dict(first.data),
            digest=first.digest,
        )
        result = self.preview_saved(msr)
        self.assertFalse(result.candidate_complete)
        self.assertFalse(result.installation_authorized)

    def test_conflicting_saved_serial_blocks(self):
        from .equipment_serial_capture_service import SERIAL_KIND
        from .documents import canonical_hash
        from .models import ProjectEvidence
        msr = self.prepare()
        first = self.save_serial(msr, 1, "GOODMAN-A")
        self.save_serial(msr, 2, "GOODMAN-B")
        payload = dict(first.data)
        payload["unit_id"] = "ROW-001-UNIT-002"
        ProjectEvidence.objects.create(
            msr=msr,
            kind=SERIAL_KIND,
            created_by=first.created_by,
            data=payload,
            digest=canonical_hash(payload),
        )
        result = self.preview_saved(msr)
        self.assertFalse(result.candidate_complete)
        self.assertFalse(result.installation_authorized)

    def test_revised_msr_excludes_old_saved_serials(self):
        msr = self.prepare()
        self.save_serial(msr, 1, "GOODMAN-A")
        self.save_serial(msr, 2, "GOODMAN-B")
        self.assertTrue(self.preview_saved(msr).candidate_complete)
        revised = self.make_synthetic_approved_revision(msr)
        self.assertFalse(self.preview_saved(msr).candidate_complete)
        self.assertFalse(self.preview_saved(revised).candidate_complete)

    def test_capture_after_installation_start_blocks(self):
        from .equipment_recorded_readiness_preview import (
            preview_recorded_equipment,
        )
        msr = self.prepare()
        first = self.save_serial(msr, 1, "GOODMAN-A")
        self.save_serial(msr, 2, "GOODMAN-B")
        result = preview_recorded_equipment(
            project_id=self.project.pk,
            msr_id=msr.pk,
            installation_starts_at=first.created_at - timedelta(seconds=1),
        )
        self.assertFalse(result.candidate_complete)
        self.assertFalse(result.installation_authorized)

    def test_readonly_preview_preserves_database_counts(self):
        from .models import AuditEvent, ProjectEvidence
        msr = self.prepare()
        self.save_serial(msr, 1, "GOODMAN-A")
        self.save_serial(msr, 2, "GOODMAN-B")
        before = (
            AuditEvent.objects.count(),
            ProjectEvidence.objects.count(),
        )
        result = self.preview_saved(msr)
        after = (
            AuditEvent.objects.count(),
            ProjectEvidence.objects.count(),
        )
        self.assertTrue(result.candidate_complete, result.blockers)
        self.assertEqual(before, after)
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.installation_authorized)