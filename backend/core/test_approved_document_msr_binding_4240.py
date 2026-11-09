"""Isolated read-only MSR identity and version-binding regressions."""
from copy import deepcopy
from types import SimpleNamespace
from django.test import SimpleTestCase

from .approved_document_msr_binding_4240 import (
    BindingDenied, inspect_approved_msr_binding,
)


class ApprovedMSRBinding4240Tests(SimpleTestCase):
    def setUp(self):
        self.project = SimpleNamespace(
            pk="project-4240",
            current_approved_id="msr-4240",
            state="ACTIVE",
        )
        self.msr = SimpleNamespace(
            pk="msr-4240",
            project_id="project-4240",
            status="APPROVED",
            number=3,
            snapshot={
                "customer": "FICTIONAL CUSTOMER",
                "financing_type": "NON_FINANCED",
                "discount": "0.00",
            },
        )

    def inspect(self):
        return inspect_approved_msr_binding(self.project, self.msr)

    def test_current_approved_version_produces_review_binding(self):
        report = self.inspect()
        self.assertEqual(report.version, 3)
        self.assertEqual(report.project_id, "project-4240")
        self.assertEqual(report.msr_id, "msr-4240")
        self.assertTrue(report.review_only)
        self.assertEqual(len(report.snapshot_sha256), 64)

    def test_historical_version_denied(self):
        self.project.current_approved_id = "newer-msr"
        with self.assertRaises(BindingDenied):
            self.inspect()

    def test_draft_version_denied(self):
        self.msr.status = "DRAFT"
        with self.assertRaises(BindingDenied):
            self.inspect()

    def test_cross_project_binding_denied(self):
        self.msr.project_id = "different-project"
        with self.assertRaises(BindingDenied):
            self.inspect()

    def test_cancelled_project_denied(self):
        self.project.state = "CANCELLED"
        with self.assertRaises(BindingDenied):
            self.inspect()

    def test_missing_financing_denied(self):
        self.msr.snapshot.pop("financing_type")
        with self.assertRaises(BindingDenied):
            self.inspect()

    def test_source_snapshot_not_modified(self):
        before = deepcopy(self.msr.snapshot)
        self.inspect()
        self.assertEqual(self.msr.snapshot, before)

    def test_invalid_version_denied(self):
        self.msr.number = 0
        with self.assertRaises(BindingDenied):
            self.inspect()

    def test_snapshot_fingerprint_changes_with_revision_data(self):
        original = self.inspect().snapshot_sha256
        self.msr.snapshot["discount"] = "25.00"
        self.assertNotEqual(
            original, self.inspect().snapshot_sha256
        )