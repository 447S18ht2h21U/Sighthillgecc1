"""Isolated authorization and PDF tests for development preview."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from pypdf import PdfReader
from rest_framework.test import APIRequestFactory, force_authenticate

from .fictional_document_preview_api_4525 import (
    KINDS,
    fictional_document_preview,
    generate_fictional_preview,
)


@override_settings(DEBUG=True)
class FictionalPreviewAPI4525Tests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def request(self, kind, role="SALES_MANAGER", authenticated=True,
                method="GET"):
        path = f"/api/fictional-document-previews/{kind}/"
        req = (
            self.factory.get(path)
            if method == "GET"
            else self.factory.post(path)
        )
        if authenticated:
            user = SimpleNamespace(
                pk=uuid4(),
                role=role,
                is_authenticated=True,
                is_active=True,
            )
            force_authenticate(req, user=user)
        return fictional_document_preview(req, kind)

    def test_all_three_fictional_documents_render(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                response = self.request(kind)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/pdf")
                pdf = PdfReader(BytesIO(response.content), strict=True)
                self.assertEqual(len(pdf.pages), 1)
                text = pdf.pages[0].extract_text() or ""
                self.assertIn("FICTIONAL AVERY SAMPLE", text)
                self.assertIn("NOT SIGNED OR AUTHORIZED", text)
                self.assertIn("Customer Signature:", text)

    def test_anonymous_is_denied(self):
        response = self.request("EXPEDITED_SERVICE", authenticated=False)
        self.assertIn(response.status_code, (401, 403))

    def test_unapproved_role_denied(self):
        for role in ("TECHNICIAN", "INSTALLATION_MANAGER", "CEO", "DBA"):
            with self.subTest(role=role):
                self.assertEqual(
                    self.request("COMPLETION_FINANCED", role=role).status_code,
                    404,
                )

    def test_unknown_kind_denied(self):
        self.assertEqual(self.request("AGREEMENT").status_code, 404)

    def test_post_not_allowed(self):
        self.assertEqual(
            self.request("EXPEDITED_SERVICE", method="POST").status_code,
            405,
        )

    @override_settings(DEBUG=False)
    def test_production_debug_gate_denied(self):
        self.assertEqual(self.request("COMPLETION_FINANCED").status_code, 404)

    @override_settings(ENVIRONMENT="production")
    def test_production_environment_denied(self):
        self.assertEqual(self.request("COMPLETION_FINANCED").status_code, 404)

    def test_postgresql_environment_denied(self):
        with patch.dict(
            "os.environ", {"PGHOST": "postgres.example.invalid"}
        ):
            self.assertEqual(
                self.request("COMPLETION_FINANCED").status_code,
                404,
            )

    def test_output_is_private_and_noncacheable(self):
        response = self.request("EXPEDITED_SERVICE")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("FICTIONAL", response["Content-Disposition"])

    def test_pdf_render_does_not_mutate_fixture(self):
        from copy import deepcopy
        from .fictional_document_preview_api_4525 import FICTIONAL_SNAPSHOT
        before = deepcopy(FICTIONAL_SNAPSHOT)
        generate_fictional_preview("COMPLETION_NON_FINANCED")
        self.assertEqual(before, FICTIONAL_SNAPSHOT)
