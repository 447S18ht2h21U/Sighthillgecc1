"""Cross-document integrity and immutable-provenance acceptance.

Fictional customer only, disposable database, no operational delivery.
"""
from copy import deepcopy
from dataclasses import replace

from django.test import TestCase

from .approved_document_lifecycle_4248 import LifecycleDenied
from .approved_document_lifecycle_integration_4249 import (
    inspect_integrated_document_lifecycle,
)
from .approved_document_version_lock_4250 import (
    inspect_version_locked_review,
)
from .approved_six_document_batch_4236 import KINDS
from .models import Document
from .test_approved_document_lifecycle_integration_4249 import (
    RealLifecycleIntegration4249Tests,
)


class SixPDFIntegrity4272Tests(TestCase):
    def setUp(self):
        RealLifecycleIntegration4249Tests.setUp(self)
        RealLifecycleIntegration4249Tests.prepare_no_promotion(self)
        self.original_snapshot = deepcopy(self.full_msr.snapshot)
        self.batch = RealLifecycleIntegration4249Tests.render(self)

    def assert_no_operational_side_effects(self):
        self.full_msr.refresh_from_db()
        self.assertEqual(
            self.full_msr.snapshot, self.original_snapshot
        )
        self.assertEqual(Document.objects.count(), 0)

    def test_01_tampering_with_any_pdf_is_denied(self):
        self.assertEqual(set(self.batch["pdfs"]), set(KINDS))

        for kind in KINDS:
            with self.subTest(document=kind):
                corrupted = {
                    **self.batch,
                    "pdfs": dict(self.batch["pdfs"]),
                }
                corrupted["pdfs"][kind] += b"unauthorized-change"

                with self.assertRaises(LifecycleDenied):
                    inspect_integrated_document_lifecycle(corrupted)

        self.assert_no_operational_side_effects()
        print("PASS: Tampering rejected separately for all six PDFs.")

    def test_02_wrong_project_msr_version_and_hash_are_denied(self):
        original_record = self.batch["record"]

        mismatches = (
            ("project_id", "wrong-project-4272"),
            ("msr_id", "wrong-msr-4272"),
            ("version", original_record.version + 1),
            ("snapshot_sha256", "0" * 64),
            (
                "financing_type",
                "NON_FINANCED"
                if original_record.financing_type == "FINANCED"
                else "FINANCED",
            ),
        )

        for field, incorrect in mismatches:
            with self.subTest(mismatched_field=field):
                forged = {
                    **self.batch,
                    "record": replace(
                        original_record, **{field: incorrect}
                    ),
                }
                with self.assertRaises(LifecycleDenied):
                    inspect_version_locked_review(
                        project=self.project,
                        msr=self.full_msr,
                        batch=forged,
                    )

        self.assert_no_operational_side_effects()
        print("PASS: Wrong project, MSR, version, hash, financing denied.")

    def test_03_valid_previews_never_authorize_operations(self):
        result = inspect_version_locked_review(
            project=self.project,
            msr=self.full_msr,
            batch=self.batch,
        )

        self.assertEqual(len(result.documents), 6)
        self.assertTrue(
            all(item.preview_verified for item in result.documents)
        )
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.project_completion_authorized)

        for item in result.documents:
            with self.subTest(document=item.kind):
                self.assertFalse(item.signed_evidence_verified)
                self.assertFalse(item.customer_delivery_verified)
                self.assertFalse(item.completion_evidence_verified)

        self.assert_no_operational_side_effects()
        print("PASS: Six previews do not grant operational authority.")