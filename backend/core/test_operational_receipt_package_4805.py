"""Operational draft Receipt status: isolated, read-only acceptance."""

from unittest.mock import patch

from django.db import connections, router
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from . import test_receipt_draft_retention_4803 as foundation
from .models import ReceiptDraftPackage, Role, User
from .operational_project_api import OperationalProjectViewSet


@override_settings(DEBUG=True, ENVIRONMENT="development")
class OperationalDraftReceiptStatus4805(TestCase):
    setUp = foundation.DraftRetentionAcceptance4803.setUp
    prepare_real_evidence = (
        foundation.DraftRetentionAcceptance4803.prepare_real_evidence
    )
    decide = foundation.DraftRetentionAcceptance4803.decide
    prepare_pair = foundation.DraftRetentionAcceptance4803.prepare_pair
    prepare_package = foundation.DraftRetentionAcceptance4803.prepare_package
    retain = foundation.DraftRetentionAcceptance4803.retain

    def request_status(self, actor):
        request = APIRequestFactory().get(
            f"/api/operational-projects/"
            f"{self.project.pk}/draft-receipt-package/"
        )
        if actor is not None:
            force_authenticate(request, user=actor)

        view = OperationalProjectViewSet.as_view({
            "get": "draft_receipt_package"
        })
        return view(request, pk=str(self.project.pk))

    def test_real_retained_package_visible_as_draft_only(self):
        package = self.prepare_package()
        record, created = self.retain(package)
        self.assertTrue(created)

        response = self.request_status(self.comptroller)
        self.assertEqual(response.status_code, 200)

        data = response.data

        self.assertEqual(data["status"], "VERIFIED_DRAFT_RETAINED")
        self.assertTrue(data["integrity_verified"])
        self.assertEqual(data["draft_package_count"], 1)
        self.assertEqual(data["verified_draft_package_count"], 1)

        for field in (
            "final_receipt_verified",
            "issuance_authorized",
            "provider_email_authenticated",
            "customer_delivery_verified",
            "completion_authorized",
        ):
            self.assertIs(data[field], False)

        self.assertNotIn("content", data)
        self.assertNotIn("archive", data)
        self.assertNotIn("pdf_bytes", data)

        self.assertEqual(ReceiptDraftPackage.objects.count(), 1)
        self.assertEqual(record.msr_id, self.msr.pk)
        print("PASS: Retained real draft visible without PDF data.")
        print("PASS: All customer authority flags remain false.")

    def test_unauthorized_role_denied(self):
        unauthorized = (
            User.objects.filter(is_active=True)
            .exclude(role__in=[Role.CEO, Role.COMPTROLLER])
            .first()
        )
        self.assertIsNotNone(unauthorized)

        response = self.request_status(unauthorized)
        self.assertIn(response.status_code, (403, 404))

        self.assertEqual(ReceiptDraftPackage.objects.count(), 0)
        print("PASS: Unauthorized role denied package status.")

    def test_missing_migration_table_safe(self):
        alias = router.db_for_read(ReceiptDraftPackage)
        connection = connections[alias]

        with patch.object(
            connection.introspection,
            "table_names",
            return_value=[],
        ):
            response = self.request_status(self.comptroller)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "SCHEMA_UNAVAILABLE")
        self.assertIs(response.data["storage_available"], False)
        self.assertIs(response.data["issuance_authorized"], False)
        print("PASS: Missing 0084 schema returns safe status.")

    def test_tampered_evidence_fails_closed(self):
        package = self.prepare_package()
        self.retain(package)

        with patch(
            "core.receipt_draft_retention_4803."
            "verify_receipt_package_draft",
            side_effect=ValueError("FICTIONAL CORRUPTION"),
        ):
            response = self.request_status(self.comptroller)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "INTEGRITY_FAILED")
        self.assertIs(response.data["integrity_verified"], False)
        self.assertIs(response.data["completion_authorized"], False)
        print("PASS: Invalid retained evidence cannot be promoted.")
