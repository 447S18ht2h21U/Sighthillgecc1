"""Real-record, isolated API integration tests.

The permission-granted cases patch only the effective-permission decision.
All account, ownership, status, and payment queries use actual test records.
The API function is intentionally not registered in live URL routing.
"""

from unittest.mock import patch

from rest_framework.test import APIRequestFactory, force_authenticate

from .test_access_compensation_disclosure import CompensationDisclosureTests
from .own_contractor_payment_api import own_contractor_payment_history


class ContractorPaymentHTTPIntegrationTests(CompensationDisclosureTests):
    """Reuse real contractor and payment fixtures and existing regression tests."""

    def _response(self, actor, method="get"):
        factory = APIRequestFactory()
        request = getattr(factory, method)("/api/own-contractor-payments/")
        if actor is not None:
            force_authenticate(request, user=actor)
        return own_contractor_payment_history(request)

    def test_http_no_effective_permission_denied(self):
        self._approve_contractor(self.contractor_record_a)
        response = self._response(self.user_a)
        self.assertEqual(response.status_code, 403)

    def test_http_granted_permission_shows_only_own_approved_payment(self):
        self._approve_contractor(self.contractor_record_a)
        self._approve_contractor(self.contractor_record_b)

        with patch(
            "core.access_compensation_report_permissions.has_permission",
            return_value=True,
        ) as permission:
            response = self._response(self.user_a)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {record["record_id"] for record in response.data["results"]},
            {str(self.contractor_record_a.pk)},
        )
        self.assertEqual(response.data["results"][0]["status"], "APPROVED")
        permission.assert_called_once()
        self.assertEqual(permission.call_args.args[1], "compensation.own.view")

    def test_http_granted_permission_hides_drafts(self):
        with patch(
            "core.access_compensation_report_permissions.has_permission",
            return_value=True,
        ):
            response = self._response(self.user_a)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_http_granted_permission_reports_paid_not_just_approved(self):
        self._pay_contractor(self.contractor_record_a)
        with patch(
            "core.access_compensation_report_permissions.has_permission",
            return_value=True,
        ):
            response = self._response(self.user_a)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["status"], "PAID")
        self.assertEqual(response.data["results"][0]["status_label"], "Paid")

    def test_http_granted_permission_excludes_internal_evidence(self):
        self._approve_contractor(self.contractor_record_a)
        with patch(
            "core.access_compensation_report_permissions.has_permission",
            return_value=True,
        ):
            response = self._response(self.user_a)
        self.assertEqual(response.status_code, 200)
        record = response.data["results"][0]
        self.assertEqual(set(record), {
            "record_type", "record_id", "period_start", "period_end",
            "kind", "status", "status_label", "basis_amount",
            "deduction_amount", "final_amount",
        })
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_http_inactive_account_denied_even_if_permission_simulated(self):
        self.user_a.is_active = False
        self.user_a.save(update_fields=["is_active"])
        with patch(
            "core.access_compensation_report_permissions.has_permission",
            return_value=True,
        ) as permission:
            response = self._response(self.user_a)
        self.assertEqual(response.status_code, 403)
        permission.assert_not_called()

    def test_http_unlinked_account_has_no_other_payments(self):
        self._approve_contractor(self.contractor_record_a)
        with patch(
            "core.access_compensation_report_permissions.has_permission",
            return_value=True,
        ):
            response = self._response(self.unlinked)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])