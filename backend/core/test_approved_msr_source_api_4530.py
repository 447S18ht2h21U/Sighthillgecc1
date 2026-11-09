"""Isolated tests of approved-MSR document-source access."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.http import Http404
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .approved_msr_source_api_4530 import (
    approved_msr_source,
    approved_source_payload,
)


def fixture_project(
    status="APPROVED",
    same_project=True,
    approved=True,
):
    project_id = uuid4()
    msr = SimpleNamespace(
        id=uuid4(),
        project_id=project_id if same_project else uuid4(),
        status=status,
        approved_at="2026-11-08" if approved else None,
        approved_by_id=uuid4() if approved else None,
        number=2,
        snapshot={
            "customer": "FICTIONAL AVERY SAMPLE",
            "project_location": "123 Fictional Lane",
            "project_city": "Sample City",
            "project_state": "MD",
            "project_zip": "00000",
            "financing_type": "FINANCED",
            "base_price": "12000.00",
            "total_price": "11000.00",
            "equipment": [{"description": "FICTIONAL HEAT PUMP"}],
        },
    )
    return SimpleNamespace(
        id=project_id,
        code="TEST-001",
        current_approved=msr,
        pending=SimpleNamespace(
            snapshot={"customer": "PENDING DRAFT MUST NOT APPEAR"}
        ),
    )


class ApprovedMSRSource4530Tests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.project = fixture_project()

    def request(self, project=None, role="COMPTROLLER",
                authenticated=True, method="GET"):
        identifier = self.project.id
        path = f"/api/development-approved-msr-source/{identifier}/"
        req = (
            self.factory.get(path)
            if method == "GET"
            else self.factory.post(path)
        )
        if authenticated:
            actor = SimpleNamespace(
                pk=uuid4(),
                is_authenticated=True,
                is_active=True,
                role=role,
            )
            force_authenticate(req, user=actor)

        scope = MagicMock()
        scope.filter.return_value.select_related.return_value.first.return_value = (
            self.project if project is None else project
        )

        with patch(
            "core.approved_msr_source_api_4530.project_scope",
            return_value=scope,
        ) as mocked:
            response = approved_msr_source(req, identifier)
            if authenticated and method == "GET" and role in (
                "COMPTROLLER", "SALES_MANAGER", "SALES_ASSOCIATE"
            ):
                if response.status_code == 200:
                    mocked.assert_called_once()
                    scope.filter.assert_called_once_with(pk=identifier)

        return response

    @override_settings(DEBUG=True)
    def test_current_approved_msr_is_source(self):
        response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["source"], "CURRENT_APPROVED_MSR")
        self.assertEqual(response.data["msr_number"], 2)
        self.assertEqual(
            response.data["fields"]["customer"], "FICTIONAL AVERY SAMPLE"
        )
        self.assertEqual(response.data["equipment_count"], 1)
        self.assertNotIn(
            "PENDING DRAFT MUST NOT APPEAR", str(response.data)
        )
        self.assertFalse(response.data["document_generation_authorized"])

    def test_payload_rejects_draft_approved_reference(self):
        with self.assertRaises(Http404):
            approved_source_payload(fixture_project(status="DRAFT"))

    def test_payload_rejects_wrong_project(self):
        with self.assertRaises(Http404):
            approved_source_payload(fixture_project(same_project=False))

    def test_payload_rejects_missing_approval_evidence(self):
        with self.assertRaises(Http404):
            approved_source_payload(fixture_project(approved=False))

    def test_payload_rejects_missing_approved_msr(self):
        project = fixture_project()
        project.current_approved = None
        with self.assertRaises(Http404):
            approved_source_payload(project)

    @override_settings(DEBUG=True)
    def test_other_roles_denied(self):
        for role in ("TECHNICIAN", "CEO", "INSTALLATION_MANAGER", "DBA"):
            with self.subTest(role=role):
                self.assertEqual(
                    self.request(role=role).status_code, 404
                )

    @override_settings(DEBUG=True)
    def test_anonymous_denied(self):
        self.assertIn(
            self.request(authenticated=False).status_code,
            (401, 403),
        )

    @override_settings(DEBUG=True)
    def test_project_not_in_scope_denied(self):
        scope = MagicMock()
        scope.filter.return_value.select_related.return_value.first.return_value = None
        req = self.factory.get(
            f"/api/development-approved-msr-source/{self.project.id}/"
        )
        force_authenticate(req, user=SimpleNamespace(
            pk=uuid4(), role="COMPTROLLER",
            is_authenticated=True, is_active=True,
        ))
        with patch(
            "core.approved_msr_source_api_4530.project_scope",
            return_value=scope,
        ):
            response = approved_msr_source(req, self.project.id)
        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=True)
    def test_post_denied(self):
        self.assertEqual(self.request(method="POST").status_code, 405)

    @override_settings(DEBUG=False)
    def test_non_development_debug_denied(self):
        self.assertEqual(self.request().status_code, 404)

    @override_settings(DEBUG=True, ENVIRONMENT="production")
    def test_production_environment_denied(self):
        self.assertEqual(self.request().status_code, 404)

    @override_settings(DEBUG=True)
    def test_response_noncacheable(self):
        response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
