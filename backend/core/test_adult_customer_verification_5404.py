"""Isolated adult-verification authorization and privacy tests."""

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from . import tests as foundation
from .adult_customer_verification_5401 import adult_verification, ACTION
from .models import AuditEvent


@override_settings(DEBUG=True)
class AdultCustomerVerification5404Tests(TestCase):
    setUp = foundation.FoundationTests.setUp
    edit_submit = foundation.FoundationTests.edit_submit
    approve = foundation.FoundationTests.approve

    def call(self, actor, method="POST", payload=None):
        path = (
            "/api/projects/"
            + str(self.project.pk)
            + "/adult-verification/"
        )
        factory = APIRequestFactory()
        if method == "GET":
            request = factory.get(path)
        else:
            request = factory.post(path, payload or {}, format="json")
        force_authenticate(request, user=actor)
        return adult_verification(request, project_id=self.project.pk)

    def ready(self):
        self.approve()
        self.project.refresh_from_db()

    def test_synthetic_evidence_is_explicitly_labeled(self):
        import os
        from unittest.mock import patch
        self.ready()
        with patch(
            "core.adult_customer_verification_5401.SYNTHETIC_PROJECT_CODE",
            self.project.code,
        ), patch.dict(os.environ, {"GECC_DEV": "1"}):
            response = self.call(
                self.sales, payload={"synthetic": True}
            )
            self.assertEqual(response.status_code, 201)
            self.assertTrue(response.data["synthetic"])
            self.assertEqual(response.data["state_of_issue"], "SYNTHETIC")
            self.assertTrue(
                AuditEvent.objects.filter(
                    action="customer.synthetic_adult_test_evidence"
                ).exists()
            )

    def test_synthetic_evidence_is_denied_for_other_projects(self):
        self.ready()
        response = self.call(
            self.sales, payload={"synthetic": True}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            AuditEvent.objects.filter(
                action="customer.synthetic_adult_test_evidence"
            ).exists()
        )

    def test_synthetic_evidence_is_denied_outside_debug(self):
        import os
        from unittest.mock import patch
        self.ready()
        with patch(
            "core.adult_customer_verification_5401.SYNTHETIC_PROJECT_CODE",
            self.project.code,
        ), patch.dict(os.environ, {"GECC_DEV": "1"}), override_settings(DEBUG=False):
            response = self.call(
                self.sales, payload={"synthetic": True}
            )
            self.assertEqual(response.status_code, 403)

    def test_assigned_associate_records_verified_attestation(self):
        self.ready()
        response = self.call(
            self.sales,
            payload={"state_of_issue": "MD", "adult_confirmed": True},
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["recorded"])
        self.assertEqual(response.data["state_of_issue"], "MD")
        self.assertEqual(response.data["employee_id"], str(self.sales.pk))
        self.assertEqual(
            AuditEvent.objects.filter(action=ACTION).count(), 1
        )

    def test_manager_cannot_attest_for_sales_associate(self):
        self.ready()
        response = self.call(
            self.manager,
            payload={"state_of_issue": "MD", "adult_confirmed": True},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AuditEvent.objects.filter(action=ACTION).exists())

    def test_license_number_is_rejected_and_not_audited(self):
        self.ready()
        response = self.call(
            self.sales,
            payload={
                "state_of_issue": "MD",
                "adult_confirmed": True,
                "license_number": "SYNTHETIC-NOT-REAL",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AuditEvent.objects.filter(action=ACTION).exists())

    def test_confirmation_must_be_explicit(self):
        self.ready()
        response = self.call(
            self.sales,
            payload={"state_of_issue": "MD", "adult_confirmed": False},
        )
        self.assertEqual(response.status_code, 400)

    def test_duplicate_submission_reuses_original_evidence(self):
        self.ready()
        payload = {"state_of_issue": "MD", "adult_confirmed": True}
        first = self.call(self.sales, payload=payload)
        second = self.call(self.sales, payload=payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            first.data["evidence_id"], second.data["evidence_id"]
        )
        self.assertEqual(
            AuditEvent.objects.filter(action=ACTION).count(), 1
        )

    def test_manager_can_read_attestation_without_changing_it(self):
        self.ready()
        self.call(
            self.sales,
            payload={"state_of_issue": "MD", "adult_confirmed": True},
        )
        response = self.call(self.manager, method="GET")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["recorded"])
        self.assertEqual(response.data["employee_id"], str(self.sales.pk))
        self.assertNotIn("license_number", response.data)
