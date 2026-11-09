"""Isolated authorization and approved-record review regressions."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from .approved_document_msr_binding_4240 import BindingDenied
from .approved_document_record_adapter_4241 import (
    DocumentReviewDenied,
    inspect_authorized_document_record,
)


class DocumentRecordAdapter4241Tests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(pk="actor-4241")
        self.project = SimpleNamespace(
            pk="project-4241",
            current_approved_id="msr-4241",
            state="ACTIVE",
        )
        self.msr = SimpleNamespace(
            pk="msr-4241",
            project_id="project-4241",
            status="APPROVED",
            number=2,
            snapshot={
                "customer": "FICTIONAL CUSTOMER",
                "financing_type": "FINANCED",
                "discount": "0.00",
            },
        )

    def review(self):
        return inspect_authorized_document_record(
            actor=self.actor, project=self.project, msr=self.msr
        )

    @patch("core.services.authorize")
    def test_authorized_record_produces_review_only(self, authorize):
        result = self.review()
        authorize.assert_called_once_with(
            self.actor, self.project, approval=True
        )
        self.assertEqual(result.version, 2)
        self.assertEqual(result.financing_type, "FINANCED")
        self.assertEqual(len(result.snapshot_sha256), 64)
        self.assertTrue(result.review_only)
        self.assertFalse(result.release_authorized)

    @patch("core.services.authorize", side_effect=PermissionDenied)
    def test_permission_denial_fails_closed(self, authorize):
        with self.assertRaises(PermissionDenied):
            self.review()
        authorize.assert_called_once()

    @patch("core.services.authorize")
    def test_historical_version_denied(self, authorize):
        self.project.current_approved_id = "newer-msr"
        with self.assertRaises(BindingDenied):
            self.review()

    @patch("core.services.authorize")
    def test_cross_project_msr_denied(self, authorize):
        self.msr.project_id = "other-project"
        with self.assertRaises(BindingDenied):
            self.review()

    @patch("core.services.authorize")
    def test_draft_msr_denied(self, authorize):
        self.msr.status = "DRAFT"
        with self.assertRaises(BindingDenied):
            self.review()

    @patch("core.services.authorize")
    def test_cancelled_project_denied(self, authorize):
        self.project.state = "CANCELLED"
        with self.assertRaises(BindingDenied):
            self.review()

    @patch("core.services.authorize")
    def test_no_actor_denied(self, authorize):
        self.actor = None
        with self.assertRaises(DocumentReviewDenied):
            self.review()
        authorize.assert_not_called()

    @patch("core.services.authorize")
    def test_source_snapshot_unchanged(self, authorize):
        before = deepcopy(self.msr.snapshot)
        self.review()
        self.assertEqual(before, self.msr.snapshot)

    @patch("core.services.authorize")
    def test_financing_classification_preserved(self, authorize):
        self.msr.snapshot["financing_type"] = "NON_FINANCED"
        result = self.review()
        self.assertEqual(result.financing_type, "NON_FINANCED")
        self.assertFalse(result.release_authorized)