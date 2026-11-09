"""Focused fail-closed tests for the six-document preview gateway."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from .approved_document_preview_gateway_4235 import (
    DOCUMENT_KINDS, GATE_VARIABLE,
    PreviewDenied, build_fictional_preview,
)


def fictional_pdf():
    out = BytesIO()
    pen = canvas.Canvas(out, pagesize=(612, 792))
    pen.drawString(40, 700, "FICTIONAL DEVELOPMENT PREVIEW")
    pen.save()
    return out.getvalue()


class ApprovedDocumentPreviewGateway4235Tests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.snapshot = {
            "customer": "FICTIONAL CUSTOMER",
            "financing_type": "NON_FINANCED",
        }
        self.details = {"project_code": "TEST-4235"}

    def build(self, kind="COMPLETION_NON_FINANCED", **overrides):
        args = {
            "kind": kind,
            "directory": self.directory,
            "snapshot": self.snapshot,
            "details": self.details,
            "review_only": True,
        }
        args.update(overrides)
        return build_fictional_preview(**args)

    def enabled(self):
        return patch.dict("os.environ", {
            GATE_VARIABLE: "enabled-test-only",
            "VERIDIAN_ENVIRONMENT": "development",
            "GECC_DEV": "1",
        })

    def test_all_six_document_kinds_registered(self):
        self.assertEqual(len(DOCUMENT_KINDS), 6)
        self.assertEqual(DOCUMENT_KINDS, {
            "CUSTOMER_SOW", "AGREEMENT", "INVOICE", "RECEIPT",
            "COMPLETION_FINANCED", "COMPLETION_NON_FINANCED",
        })

    def test_default_gate_denies(self):
        with patch.dict("os.environ", {
            GATE_VARIABLE: "",
            "VERIDIAN_ENVIRONMENT": "development",
            "GECC_DEV": "1",
        }):
            with self.assertRaises(PreviewDenied):
                self.build()

    def test_wrong_environment_denied(self):
        with patch.dict("os.environ", {
            GATE_VARIABLE: "enabled-test-only",
            "VERIDIAN_ENVIRONMENT": "production",
            "GECC_DEV": "1",
        }):
            with self.assertRaises(PreviewDenied):
                self.build()

    def test_unsigned_review_required(self):
        with self.enabled():
            for overrides in (
                {"review_only": False},
                {"signing_test": True},
                {"release_context": {}},
            ):
                with self.subTest(overrides=overrides):
                    with self.assertRaises(PreviewDenied):
                        self.build(**overrides)

    def test_fictional_customer_required(self):
        self.snapshot["customer"] = "REAL CUSTOMER"
        with self.enabled():
            with self.assertRaises(PreviewDenied):
                self.build()

    def test_unknown_kind_denied(self):
        with self.enabled():
            with self.assertRaises(PreviewDenied):
                self.build("UNKNOWN")

    def test_financing_mismatch_denied(self):
        with self.enabled():
            with self.assertRaises(PreviewDenied):
                self.build("COMPLETION_FINANCED")

    def test_extra_arguments_denied(self):
        self.details["release_approval"] = "YES"
        with self.enabled():
            with self.assertRaises(PreviewDenied):
                self.build()

    def test_valid_pdf_has_integrity_metadata(self):
        content = fictional_pdf()
        with self.enabled(), patch(
            "core.approved_document_preview_gateway_4235._render_selected",
            return_value=content,
        ) as renderer:
            result = self.build()

        renderer.assert_called_once()
        self.assertEqual(
            result["sha256"], sha256(content).hexdigest().upper()
        )
        self.assertEqual(result["page_count"], 1)
        self.assertTrue(result["development_only"])
        self.assertFalse(result["signed"])
        self.assertFalse(result["released"])

    def test_unmarked_pdf_denied(self):
        out = BytesIO()
        pen = canvas.Canvas(out, pagesize=(612, 792))
        pen.drawString(40, 700, "UNMARKED DOCUMENT")
        pen.save()
        with self.enabled(), patch(
            "core.approved_document_preview_gateway_4235._render_selected",
            return_value=out.getvalue(),
        ):
            with self.assertRaises(PreviewDenied):
                self.build()

    def test_invalid_renderer_output_denied(self):
        with self.enabled(), patch(
            "core.approved_document_preview_gateway_4235._render_selected",
            return_value=b"not a pdf",
        ):
            with self.assertRaises(PreviewDenied):
                self.build()

    def test_caller_snapshot_not_modified(self):
        original = dict(self.snapshot)
        with self.enabled(), patch(
            "core.approved_document_preview_gateway_4235._render_selected",
            return_value=fictional_pdf(),
        ):
            self.build()
        self.assertEqual(self.snapshot, original)

    def test_operational_renderer_not_imported_by_gateway(self):
        import inspect
        from . import approved_document_preview_gateway_4235 as gateway
        source = inspect.getsource(gateway)
        self.assertNotIn("from .documents import", source)
        self.assertNotIn("Document.objects.create", source)
        self.assertNotIn("send_receipt", source)