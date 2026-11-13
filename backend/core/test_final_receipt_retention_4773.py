"""Isolated acceptance for internal V4 Receipt document retention.

Uses Django's disposable test database. No live email or DocuSign.
The PDF/financial inputs are controlled fixtures; this suite tests
storage integrity, authorization, idempotency, and rollback.
"""

import hashlib
import os
from contextlib import ExitStack
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.db import IntegrityError, transaction
from copy import copy
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from reportlab.pdfgen import canvas
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .final_receipt_internal_retention_4770 import (
    RENDERER_VERSION,
    retain_internal_v4_receipt,
    validate_internal_receipt_document,
)
from .models import Customer, Document, MSR, Project, Role, User


SERVICE = "core.final_receipt_internal_retention_4770"


def internal_pdf():
    output = BytesIO()
    pen = canvas.Canvas(output, pagesize=(792, 612))
    pen.setFont("Helvetica-Bold", 14)
    pen.drawString(100, 400, "INTERNAL - NOT ISSUED")
    pen.showPage()
    pen.save()
    return output.getvalue()


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InternalReceiptDatabaseAcceptance4773(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.sqlite3":
            raise RuntimeError("SAFETY STOP: Non-SQLite test backend.")

    def setUp(self):
        now = timezone.now()

        self.comptroller = User.objects.create_user(
            username="receipt-comptroller-4773",
            password=None,
            role=Role.COMPTROLLER,
            initials="RC",
        )

        self.sales = User.objects.create_user(
            username="receipt-sales-4773",
            password=None,
            role=Role.SALES_ASSOCIATE,
            initials="RS",
        )

        self.customer = Customer.objects.create(
            created_at=now,
            legal_name="FICTIONAL CUSTOMER 4773",
            billing_address="123 Fictional Avenue",
            email="fictional4773@example.invalid",
            phone="555-0100",
            created_by=self.sales,
        )

        self.project = Project.objects.create(
            created_at=now,
            code="FICTIONAL-4773",
            customer=self.customer,
            location="123 Fictional Avenue",
            sales_associate=self.sales,
            reviewer=self.comptroller,
            state="ACTIVE",
        )

        self.msr = MSR.objects.create(
            created_at=now,
            project=self.project,
            number=1,
            status="APPROVED",
            snapshot={
                "total_price": "1000.00",
                "financing_type": "NON_FINANCED",
                "payment_option": "50_PERCENT_DEPOSIT",
            },
            created_by=self.sales,
            prepared_by=self.sales,
            approved_by=self.comptroller,
        )

        self.project.current_approved = self.msr
        self.project.save(update_fields=["current_approved"])

        self.pdf = internal_pdf()
        self.pdf_digest = hashlib.sha256(self.pdf).hexdigest()
        self.reference_digest = "a" * 64

    def patched_service(self, *, audit_error=None):
        stack = ExitStack()
        stack.enter_context(
            patch.dict(
                os.environ,
                {"GECC_INTERNAL_RECEIPT_RETENTION_ENABLED": "1"},
            )
        )

        stack.enter_context(
            patch(
                SERVICE + ".verify_approved_final_receipt",
                return_value=SimpleNamespace(
                    sha256=self.reference_digest,
                ),
            )
        )

        finances = SimpleNamespace(
            project_id=str(self.project.pk),
            approved_msr_id=str(self.msr.pk),
            approved_msr_version=self.msr.number,
            overpayment_requires_review=False,
            verified_customer_funds=Decimal("500.00"),
            outstanding_balance=Decimal("500.00"),
        )

        stack.enter_context(
            patch(
                SERVICE + ".assess_final_receipt_finances",
                return_value=finances,
            )
        )

        rendered = SimpleNamespace(
            status="INTERNAL_NOT_ISSUED",
            project_id=str(self.project.pk),
            approved_msr_id=str(self.msr.pk),
            reference_sha256=self.reference_digest,
            content=self.pdf,
            pdf_sha256=self.pdf_digest,
        )

        renderer = stack.enter_context(
            patch(
                SERVICE + ".render_v4_receipt_internal",
                return_value=rendered,
            )
        )

        auditor = stack.enter_context(
            patch(SERVICE + ".audit")
        )

        if audit_error is not None:
            auditor.side_effect = audit_error

        return stack, renderer, auditor

    def create_internal(self):
        return retain_internal_v4_receipt(
            actor=self.comptroller,
            project_id=self.project.pk,
        )

    def test_actual_creation_idempotency_and_immutability(self):
        with self.patched_service()[0]:
            first, created = self.create_internal()
            self.assertTrue(created)

            self.assertEqual(
                Document.objects.filter(
                    msr=self.msr,
                    kind=Document.Kind.RECEIPT,
                ).count(),
                1,
            )

            stored = Document.objects.get(pk=first.pk)

            self.assertEqual(stored.status, "PREPARATION")
            self.assertEqual(stored.renderer_version, RENDERER_VERSION)
            self.assertEqual(stored.pdf_sha256, self.pdf_digest)
            self.assertEqual(bytes(stored.content), self.pdf)
            self.assertEqual(
                stored.snapshot_sha256,
                canonical_hash(self.msr.snapshot),
            )

            self.assertTrue(
                validate_internal_receipt_document(
                    stored,
                    msr=self.msr,
                    reference_sha256=self.reference_digest,
                    snapshot_sha256=canonical_hash(
                        self.msr.snapshot
                    ),
                )
            )

            second, created_again = self.create_internal()

            self.assertFalse(created_again)
            self.assertEqual(first.pk, second.pk)
            self.assertEqual(Document.objects.count(), 1)

            stored.filename = "REPLACEMENT.pdf"

            with self.assertRaises(DjangoValidationError):
                stored.save()

            with self.assertRaises(DjangoValidationError):
                stored.delete()

        print(
            "PASS: Real insert, duplicate prevention, "
            "immutable update/delete guards."
        )

    def test_persisted_bytes_tampering_is_rejected(self):
        with self.patched_service()[0]:
            first, created = self.create_internal()
            self.assertTrue(created)

            original = Document.objects.get(pk=first.pk)
            original_bytes = bytes(original.content)
            original_digest = original.pdf_sha256

            # The database must reject a direct bulk update, even
            # though bulk updates bypass Document.save().
            # A nested savepoint contains the expected SQL error.
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Document.objects.filter(pk=first.pk).update(
                        content=original_bytes + b"ALTERED",
                    )

            preserved = Document.objects.get(pk=first.pk)
            self.assertEqual(bytes(preserved.content), original_bytes)
            self.assertEqual(preserved.pdf_sha256, original_digest)

            # Independently prove that the Receipt validator
            # rejects tampered bytes, without modifying database
            # triggers or inserting a corrupted historical record.
            altered_copy = copy(preserved)
            altered_copy.content = original_bytes + b"ALTERED"

            with self.assertRaises(ValidationError):
                validate_internal_receipt_document(
                    altered_copy,
                    msr=self.msr,
                    reference_sha256=self.reference_digest,
                    snapshot_sha256=canonical_hash(self.msr.snapshot),
                )

            second, created_again = self.create_internal()
            self.assertFalse(created_again)
            self.assertEqual(second.pk, first.pk)
            self.assertEqual(Document.objects.count(), 1)

        print(
            "PASS: Database rejects direct tampering, "
            "original PDF survives, validator rejects altered bytes."
        )

    def test_wrong_role_and_disabled_switch_denied(self):
        with self.assertRaises(PermissionDenied):
            retain_internal_v4_receipt(
                actor=self.comptroller,
                project_id=self.project.pk,
            )

        with self.patched_service()[0]:
            with self.assertRaises(PermissionDenied):
                retain_internal_v4_receipt(
                    actor=self.sales,
                    project_id=self.project.pk,
                )

        self.assertEqual(Document.objects.count(), 0)
        print("PASS: Disabled switch and unauthorized role denied.")

    def test_audit_failure_rolls_back_document(self):
        stack, _, _ = self.patched_service(
            audit_error=RuntimeError("FICTIONAL AUDIT FAILURE")
        )

        with stack:
            with self.assertRaisesRegex(
                RuntimeError,
                "FICTIONAL AUDIT FAILURE",
            ):
                self.create_internal()

        self.assertEqual(Document.objects.count(), 0)
        print("PASS: Audit failure rolls back inserted Document.")
