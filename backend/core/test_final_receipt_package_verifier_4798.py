"""Read-only ZIP verifier tested against real equipment records."""

from dataclasses import replace
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from django.test import TestCase, override_settings

from . import test_final_receipt_package_4797 as fixture
from .final_receipt_package_4797 import build_receipt_package_draft
from .final_receipt_package_verifier_4798 import (
    verify_receipt_package_draft,
)
from .models import Document, ReceiptDispatchOutbox


@override_settings(DEBUG=True, ENVIRONMENT="development")
class DraftPackageRetrievalAcceptance4798(TestCase):
    setUp = fixture.PairedDraftAcceptance4797.setUp
    prepare_real_evidence = (
        fixture.PairedDraftAcceptance4797.prepare_real_evidence
    )
    decide = fixture.PairedDraftAcceptance4797.decide
    prepare_pair = fixture.PairedDraftAcceptance4797.prepare_pair

    def valid_package(self):
        receipt, addendum, _ = self.prepare_pair()
        return build_receipt_package_draft(
            project=self.project,
            receipt=receipt,
            addendum=addendum,
        )

    def test_real_package_passes_independent_verification(self):
        package = self.valid_package()
        result = verify_receipt_package_draft(
            project=self.project,
            package=package,
        )

        self.assertTrue(result.integrity_verified)
        self.assertEqual(result.status, "DRAFT_NOT_ISSUED")
        self.assertFalse(result.issuance_authorized)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)
        self.assertEqual(Document.objects.count(), 0)
        self.assertEqual(ReceiptDispatchOutbox.objects.count(), 0)

        print("PASS: Real draft archive independently verified.")
        print("PASS: Exact serial records and MSR matched; no issuance.")

    def test_changed_archive_and_swapped_receipt_rejected(self):
        package = self.valid_package()

        with self.assertRaises(ValueError):
            verify_receipt_package_draft(
                project=self.project,
                package=replace(
                    package,
                    archive=package.archive + b"TAMPER",
                ),
            )

        with ZipFile(BytesIO(package.archive)) as original:
            entries = {
                name: original.read(name)
                for name in original.namelist()
            }

        entries["V4-Receipt-DRAFT-NOT-ISSUED.pdf"] += b"ALTERED"
        output = BytesIO()

        with ZipFile(output, "w", compression=ZIP_DEFLATED) as changed:
            for name, content in entries.items():
                changed.writestr(name, content)

        from hashlib import sha256
        changed_archive = output.getvalue()

        with self.assertRaises(ValueError):
            verify_receipt_package_draft(
                project=self.project,
                package=replace(
                    package,
                    archive=changed_archive,
                    archive_sha256=sha256(changed_archive).hexdigest(),
                ),
            )

        print("PASS: Changed archive and substituted PDF rejected.")

    def test_cross_msr_and_false_authority_rejected(self):
        package = self.valid_package()

        for altered in (
            replace(package, msr_id="FOREIGN-MSR"),
            replace(package, issuance_authorized=True),
            replace(package, customer_delivery_verified=True),
            replace(package, completion_authorized=True),
        ):
            with self.subTest(value=str(altered)):
                with self.assertRaises(ValueError):
                    verify_receipt_package_draft(
                        project=self.project,
                        package=altered,
                    )

        print("PASS: Cross-MSR and false authority rejected.")
