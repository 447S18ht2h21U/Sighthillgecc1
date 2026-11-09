"""Database-backed fictional document bridge security tests."""
from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .approved_document_msr_binding_4240 import BindingDenied
from .approved_document_record_bridge_4244 import (
    BridgeDenied, prepare_fictional_document_review,
)
from .test_approved_document_real_db_4243 import (
    RealDocumentRecord4243Tests,
)


class DocumentRecordBridge4244Tests(TestCase):
    def setUp(self):
        RealDocumentRecord4243Tests.setUp(self)

    def review(self, actor=None, msr=None):
        return prepare_fictional_document_review(
            actor=self.comptroller if actor is None else actor,
            project=self.project,
            msr=self.msr if msr is None else msr,
            directory="FICTIONAL-TEST-REFERENCE",
            created="2026-11-04",
            associate="FICTIONAL ASSOCIATE",
            invoice_number="FICTIONAL-INVOICE-4244",
            invoice_date="2026-11-04",
        )

    @patch(
        "core.approved_document_record_bridge_4244."
        "build_six_document_review"
    )
    def test_approved_record_reaches_preview_only(self, renderer):
        renderer.return_value = {
            "manifest": ("FICTIONAL-REVIEW",),
            "pdfs": {},
            "signed": False,
            "released": False,
            "customer_delivery": False,
        }
        before = deepcopy(self.msr.snapshot)
        result = self.review()

        renderer.assert_called_once()
        self.assertEqual(
            renderer.call_args.kwargs["project_code"],
            self.project.code,
        )
        self.assertEqual(
            renderer.call_args.kwargs["msr_version"], "1"
        )
        self.assertEqual(
            renderer.call_args.args[1], before
        )
        self.assertEqual(result["record"].msr_id, str(self.msr.pk))
        self.assertTrue(result["review_only"])
        self.assertFalse(result["release_authorized"])
        self.msr.refresh_from_db()
        self.assertEqual(self.msr.snapshot, before)

    @patch(
        "core.approved_document_record_bridge_4244."
        "build_six_document_review"
    )
    def test_unauthorized_user_never_reaches_renderer(self, renderer):
        with self.assertRaises(PermissionDenied):
            self.review(actor=self.outsider)
        renderer.assert_not_called()

    @patch(
        "core.approved_document_record_bridge_4244."
        "build_six_document_review"
    )
    def test_historical_version_never_reaches_renderer(self, renderer):
        self.project.current_approved_id = None
        with self.assertRaises(BindingDenied):
            self.review()
        renderer.assert_not_called()

    @patch(
        "core.approved_document_record_bridge_4244."
        "build_six_document_review"
    )
    def test_real_customer_name_rejected(self, renderer):
        # Modify only the isolated test record before approval.
        self.msr.snapshot = {
            **self.msr.snapshot,
            "customer": "ORDINARY CUSTOMER",
        }
        with self.assertRaises(BridgeDenied):
            self.review()
        renderer.assert_not_called()

    @patch(
        "core.approved_document_record_bridge_4244."
        "build_six_document_review"
    )
    def test_operational_output_state_rejected(self, renderer):
        renderer.return_value = {
            "manifest": (),
            "pdfs": {},
            "signed": False,
            "released": True,
            "customer_delivery": False,
        }
        with self.assertRaises(BridgeDenied):
            self.review()