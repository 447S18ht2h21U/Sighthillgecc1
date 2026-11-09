"""Tests for pre-send ordering and fail-closed authorization."""
import hashlib
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.mail import get_connection
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .receipt_secure_test_workflow import secure_test_receipt_dispatch
from .receipt_predispatch_guard import ReceiptPredispatchApproval


class SecureReceiptWorkflowTests(SimpleTestCase):
    def setUp(self):
        self.pdf = b"%PDF-1.4\nsecure fixture\n%%EOF"
        self.project_id = uuid4()
        self.document_id = uuid4()
        self.actor = SimpleNamespace(pk=uuid4())
        self.approval = ReceiptPredispatchApproval(
            project_id=str(self.project_id),
            msr_id=str(uuid4()),
            document_id=str(self.document_id),
            recipient="customer@example.com",
            pdf_sha256=hashlib.sha256(self.pdf).hexdigest(),
        )
        self.values = dict(
            actor=self.actor,
            project_id=self.project_id,
            document_id=self.document_id,
            recipient="customer@example.com",
            pdf_bytes=self.pdf,
            observed_sent_at=timezone.now() - timedelta(minutes=1),
            connection=get_connection(
                backend="django.core.mail.backends.locmem.EmailBackend"
            ),
            provider_reference="TEST-4137",
        )

    def invoke(self, approval=None, failure=None, **changes):
        values = dict(self.values)
        values.update(changes)
        record = SimpleNamespace(status="UNVERIFIED")
        with patch(
            "core.receipt_secure_test_workflow."
            "validate_receipt_before_dispatch",
            return_value=self.approval if approval is None else approval,
            side_effect=failure,
        ) as gate, patch(
            "core.receipt_secure_test_workflow."
            "dispatch_and_observe_test_receipt",
            return_value=record,
        ) as send:
            try:
                result = secure_test_receipt_dispatch(**values)
                return result, gate.call_count, send.call_count
            finally:
                self.calls = (gate.call_count, send.call_count)
                self.send_args = send.call_args

    def test_authorized_candidate_reaches_test_dispatch(self):
        result, gated, sent = self.invoke()
        self.assertEqual((gated, sent), (1, 1))
        self.assertEqual(result.status, "UNVERIFIED")
        self.assertEqual(
            self.send_args.kwargs["expected_sha256"],
            self.approval.pdf_sha256,
        )

    def test_permission_denial_prevents_dispatch(self):
        with self.assertRaises(PermissionDenied):
            self.invoke(failure=PermissionDenied("Denied"))
        self.assertEqual(self.calls, (1, 0))
        self.assertEqual(len(mail.outbox), 0)

    def test_pdf_denial_prevents_dispatch(self):
        with self.assertRaises(ValidationError):
            self.invoke(failure=ValidationError("Wrong PDF"))
        self.assertEqual(self.calls, (1, 0))
        self.assertEqual(len(mail.outbox), 0)

    def test_wrong_customer_denial_prevents_dispatch(self):
        with self.assertRaises(ValidationError):
            self.invoke(failure=ValidationError("Wrong recipient"))
        self.assertEqual(self.calls, (1, 0))

    def test_no_email_backend_rejected_before_gate(self):
        with self.assertRaises(ValidationError):
            self.invoke(connection=None)
        self.assertEqual(self.calls, (0, 0))

    def test_wrong_project_binding_rejected(self):
        from dataclasses import replace
        approval = replace(self.approval, project_id=str(uuid4()))
        with self.assertRaises(ValidationError):
            self.invoke(approval=approval)
        self.assertEqual(self.calls, (1, 0))

    def test_wrong_document_binding_rejected(self):
        from dataclasses import replace
        approval = replace(self.approval, document_id=str(uuid4()))
        with self.assertRaises(ValidationError):
            self.invoke(approval=approval)
        self.assertEqual(self.calls, (1, 0))

    def test_forged_provider_trust_rejected(self):
        from dataclasses import replace
        approval = replace(self.approval, provider_authenticated=True)
        with self.assertRaises(ValidationError):
            self.invoke(approval=approval)
        self.assertEqual(self.calls, (1, 0))

    def test_forged_delivery_trust_rejected(self):
        from dataclasses import replace
        approval = replace(self.approval, delivery_verified=True)
        with self.assertRaises(ValidationError):
            self.invoke(approval=approval)
        self.assertEqual(self.calls, (1, 0))

    def test_forged_completion_authority_rejected(self):
        from dataclasses import replace
        approval = replace(self.approval, completion_authorized=True)
        with self.assertRaises(ValidationError):
            self.invoke(approval=approval)
        self.assertEqual(self.calls, (1, 0))