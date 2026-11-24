"""Isolated security and audit tests for historical draft restoration."""
from copy import deepcopy

from django.test import TestCase

from . import tests as foundation
from .models import AuditEvent, MSR
from .services import transition


class DraftRestore5705Tests(TestCase):
    def setUp(self):
        foundation.FoundationTests.setUp(self)
        self.url = f"/api/projects/{self.project.id}/restore-draft/"
        self.msr_id = str(self.project.pending_id)

        snapshot = deepcopy(self.snapshot)
        snapshot["customer"] = "Historical Fictional Customer"

        self.saved = transition(
            self.sales, self.project.pending_id,
            "edit", 0, snapshot=snapshot,
        )
        self.source = AuditEvent.objects.get(
            entity_id=self.project.id,
            action="msr.edit",
        )

    def request_data(self, **overrides):
        data = {
            "history_entry_id": str(self.source.id),
            "expected_msr_id": self.msr_id,
            "expected_sequence": 1,
            "reason": "Restore verified fictional draft",
        }
        data.update(overrides)
        return data

    def post_as(self, actor, **overrides):
        self.client.force_authenticate(actor)
        return self.client.post(
            self.url, self.request_data(**overrides),
            format="json",
        )

    def test_restore_creates_new_save_and_preserves_source(self):
        current = deepcopy(self.saved.snapshot)
        current["customer"] = "Changed After Historical Save"
        transition(
            self.sales, self.project.pending_id,
            "edit", 1, snapshot=current,
        )

        response = self.post_as(
            self.sales,
            expected_sequence=2,
        )
        self.assertEqual(response.status_code, 200, response.content)

        record = MSR.objects.get(pk=self.project.pending_id)
        self.assertEqual(record.edit_sequence, 3)
        self.assertEqual(record.status, "DRAFT")
        self.assertEqual(record.snapshot, self.saved.snapshot)

        self.source.refresh_from_db()
        self.assertEqual(
            self.source.payload["after"], self.saved.snapshot
        )

        restored = AuditEvent.objects.get(
            entity_id=self.project.id,
            action="msr.draft_restored",
        )
        self.assertEqual(
            restored.payload["source_audit_id"],
            str(self.source.id),
        )
        self.assertEqual(
            restored.payload["reason"],
            "Restore verified fictional draft",
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                entity_id=self.project.id,
                action="msr.edit",
            ).count(), 3,
        )

    def test_other_associate_cannot_restore(self):
        response = self.post_as(self.other)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            MSR.objects.get(pk=self.project.pending_id).edit_sequence,
            1,
        )

    def test_inactive_employee_cannot_restore(self):
        self.sales.is_active = False
        self.sales.save()
        response = self.post_as(self.sales)
        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(
            MSR.objects.get(pk=self.project.pending_id).edit_sequence,
            1,
        )

    def test_restoration_reason_is_mandatory(self):
        response = self.post_as(self.sales, reason="  ")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            AuditEvent.objects.filter(
                action="msr.draft_restored",
                entity_id=self.project.id,
            ).exists()
        )

    def test_stale_sequence_is_rejected(self):
        response = self.post_as(
            self.sales, expected_sequence=0
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            MSR.objects.get(pk=self.project.pending_id).edit_sequence,
            1,
        )

    def test_different_msr_identity_is_rejected(self):
        response = self.post_as(
            self.sales,
            expected_msr_id="00000000-0000-0000-0000-000000000001",
        )
        self.assertEqual(response.status_code, 400)

    def test_submitted_record_cannot_be_restored(self):
        MSR.objects.filter(pk=self.project.pending_id).update(
            status="SUBMITTED"
        )
        response = self.post_as(self.sales)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            MSR.objects.get(pk=self.project.pending_id).status,
            "SUBMITTED",
        )

    def test_approved_record_cannot_be_restored(self):
        MSR.objects.filter(pk=self.project.pending_id).update(
            status="APPROVED"
        )
        response = self.post_as(self.sales)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            MSR.objects.get(pk=self.project.pending_id).status,
            "APPROVED",
        )

    def test_unknown_fields_are_rejected(self):
        response = self.post_as(
            self.sales, bypass_approval=True
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_history_entry_is_rejected(self):
        response = self.post_as(
            self.sales,
            history_entry_id="00000000-0000-0000-0000-000000000001",
        )
        self.assertEqual(response.status_code, 404)
