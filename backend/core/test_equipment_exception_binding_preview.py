"""Isolated database tests for unregistered equipment exception binding."""
from datetime import timedelta
from django.test import override_settings
from django.utils import timezone

from .test_equipment_serial_exception_service import SerialExceptionRequestServiceTests
from .equipment_exception_binding_preview import preview_equipment_exception_binding


@override_settings(DEBUG=True, ENVIRONMENT="development")
class EquipmentExceptionBindingTests(SerialExceptionRequestServiceTests):
    def binding(self, msr, records):
        return preview_equipment_exception_binding(
            project_id=self.project.pk,
            msr_id=msr.pk,
            records=records,
            installation_starts_at=timezone.now() + timedelta(hours=1),
        )

    def equipment_record(self, msr, number, serial="", reference=""):
        return {
            "msr_id": str(msr.pk),
            "unit_id": f"ROW-001-UNIT-{number:03d}",
            "serial_number": serial,
            "exception_reference": reference,
            "recorded_at": timezone.now() - timedelta(minutes=5),
        }

    def test_approved_exception_and_second_serial_are_candidates(self):
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(request)
        result = self.binding(msr, [
            self.equipment_record(msr, 1, reference=str(decision.pk)),
            self.equipment_record(msr, 2, serial="GOODMAN-002"),
        ])
        self.assertTrue(result.candidate_complete, result.blockers)
        self.assertEqual(
            result.verified_exception_units, ("ROW-001-UNIT-001",)
        )
        self.assertFalse(result.exception_effective)
        self.assertFalse(result.installation_authorized)

    def test_unapproved_request_cannot_replace_decision(self):
        msr = self.prepare()
        request = self.request(msr)
        result = self.binding(msr, [
            self.equipment_record(msr, 1, reference=str(request.pk)),
            self.equipment_record(msr, 2, serial="GOODMAN-002"),
        ])
        self.assertFalse(result.candidate_complete)

    def test_revoked_decision_cannot_qualify(self):
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(request)
        self.revoke(decision)
        result = self.binding(msr, [
            self.equipment_record(msr, 1, reference=str(decision.pk)),
            self.equipment_record(msr, 2, serial="GOODMAN-002"),
        ])
        self.assertFalse(result.candidate_complete)

    def test_wrong_unit_decision_is_rejected(self):
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(request)
        result = self.binding(msr, [
            self.equipment_record(msr, 1, serial="GOODMAN-001"),
            self.equipment_record(msr, 2, reference=str(decision.pk)),
        ])
        self.assertFalse(result.candidate_complete)

    def test_missing_unit_still_blocks_with_valid_decision(self):
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(request)
        result = self.binding(msr, [
            self.equipment_record(msr, 1, reference=str(decision.pk)),
        ])
        self.assertFalse(result.candidate_complete)

    def test_serial_only_is_candidate_not_installation_authority(self):
        msr = self.prepare()
        result = self.binding(msr, [
            self.equipment_record(msr, 1, serial="GOODMAN-001"),
            self.equipment_record(msr, 2, serial="GOODMAN-002"),
        ])
        self.assertTrue(result.candidate_complete, result.blockers)
        self.assertFalse(result.installation_authorized)