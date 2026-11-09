"""Predispatch boundary tests with isolated mocked ORM lookups."""
import hashlib
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .models import Role
from .receipt_predispatch_guard import validate_receipt_before_dispatch


class ReceiptPredispatchGuardTests(SimpleTestCase):
    def setUp(self):
        self.pdf = b"%PDF-1.4\nretained test receipt\n%%EOF"
        self.actor = SimpleNamespace(pk=uuid4())
        self.msr = SimpleNamespace(
            pk=uuid4(), status="APPROVED", snapshot={
                "customer_email": "customer@example.com"
            },
        )
        self.project = SimpleNamespace(
            pk=uuid4(), state="ACTIVE", current_approved=self.msr
        )
        self.msr.project_id = self.project.pk
        self.document = SimpleNamespace(
            pk=uuid4(), status="PREPARATION",
            content=self.pdf,
            pdf_sha256=hashlib.sha256(self.pdf).hexdigest(),
        )
        self.user = SimpleNamespace(is_active=True, role=Role.COMPTROLLER)
        self.params = dict(
            actor=self.actor, project_id=self.project.pk,
            document_id=self.document.pk,
            recipient="customer@example.com", pdf_bytes=self.pdf,
        )

    def run_gate(self, **changes):
        params = dict(self.params)
        params.update(changes)
        with patch(
            "core.receipt_predispatch_guard.User.objects.get",
            return_value=self.user,
        ), patch(
            "core.receipt_predispatch_guard.Project.objects.select_related"
        ) as projects, patch(
            "core.receipt_predispatch_guard.Document.objects.get",
            return_value=self.document,
        ):
            projects.return_value.get.return_value = self.project
            return validate_receipt_before_dispatch(**params)

    def test_valid_candidate_is_never_delivery_proof(self):
        decision = self.run_gate()
        self.assertTrue(decision.test_only)
        self.assertFalse(decision.provider_authenticated)
        self.assertFalse(decision.delivery_verified)
        self.assertFalse(decision.completion_authorized)
        self.assertEqual(decision.pdf_sha256, self.document.pdf_sha256)

    def test_unauthenticated_denied(self):
        with self.assertRaises(PermissionDenied):
            self.run_gate(actor=None)

    def test_inactive_comptroller_denied(self):
        self.user.is_active = False
        with self.assertRaises(PermissionDenied):
            self.run_gate()

    def test_wrong_role_denied(self):
        self.user.role = Role.SALES_ASSOCIATE
        with self.assertRaises(PermissionDenied):
            self.run_gate()

    def test_unapproved_msr_denied(self):
        self.msr.status = "DRAFT"
        with self.assertRaises(ValidationError):
            self.run_gate()

    def test_foreign_project_binding_denied(self):
        self.msr.project_id = uuid4()
        with self.assertRaises(ValidationError):
            self.run_gate()

    def test_cancelled_project_denied(self):
        self.project.state = "CANCELLED"
        with self.assertRaises(ValidationError):
            self.run_gate()

    def test_wrong_recipient_denied(self):
        with self.assertRaises(ValidationError):
            self.run_gate(recipient="other@example.com")

    def test_missing_customer_email_denied(self):
        self.msr.snapshot = {"customer_email": ""}
        with self.assertRaises(ValidationError):
            self.run_gate()

    def test_different_pdf_denied(self):
        with self.assertRaises(ValidationError):
            self.run_gate(pdf_bytes=b"%PDF-1.4\nother\n%%EOF")

    def test_corrupt_stored_fingerprint_denied(self):
        self.document.pdf_sha256 = "0" * 64
        with self.assertRaises(ValidationError):
            self.run_gate()

    def test_wrong_document_status_denied(self):
        self.document.status = "SIGNED"
        with self.assertRaises(ValidationError):
            self.run_gate()