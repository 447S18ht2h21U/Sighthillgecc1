"""Isolated HTTP-boundary tests for contractor self-service history.

Mocks replace the database and established disclosure service.
Existing disclosure and ownership regression tests remain authoritative
for underlying financial-data filtering.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .own_contractor_payment_api import own_contractor_payment_history


class OwnContractorPaymentAPITests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.actor = SimpleNamespace(pk=42, is_authenticated=True)
        self.verified = SimpleNamespace(pk=42, is_active=True)

    def request(self, method="get", user=None):
        factory_method = getattr(self.factory, method)
        request = factory_method("/api/own-contractor-payments/")
        if user is not None:
            force_authenticate(request, user=user)
        return request

    def test_anonymous_request_is_denied(self):
        with patch(
            "core.own_contractor_payment_api.User.objects.filter"
        ) as lookup, patch(
            "core.own_contractor_payment_api.own_contractor_payment_disclosure"
        ) as disclosure:
            response = own_contractor_payment_history(self.request())
            self.assertIn(response.status_code, (401, 403))
            lookup.assert_not_called()
            disclosure.assert_not_called()

    def test_inactive_or_missing_account_is_denied(self):
        with patch(
            "core.own_contractor_payment_api.User.objects.filter"
        ) as lookup, patch(
            "core.own_contractor_payment_api.own_contractor_payment_disclosure"
        ) as disclosure:
            lookup.return_value.first.return_value = None
            response = own_contractor_payment_history(
                self.request(user=self.actor)
            )
            self.assertEqual(response.status_code, 403)
            lookup.assert_called_once_with(pk=42, is_active=True)
            disclosure.assert_not_called()

    def test_missing_effective_permission_blocks_disclosure(self):
        with patch(
            "core.own_contractor_payment_api.User.objects.filter"
        ) as lookup, patch(
            "core.own_contractor_payment_api.require_own_compensation_permission"
        ) as gate, patch(
            "core.own_contractor_payment_api.own_contractor_payment_disclosure"
        ) as disclosure:
            from rest_framework.exceptions import PermissionDenied

            lookup.return_value.first.return_value = self.verified
            gate.side_effect = PermissionDenied("Access denied.")
            response = own_contractor_payment_history(
                self.request(user=self.actor)
            )
            self.assertEqual(response.status_code, 403)
            gate.assert_called_once_with(self.verified)
            disclosure.assert_not_called()

    def test_approved_record_uses_existing_disclosure(self):
        allowed = [{
            "record_type": "contractor_payment",
            "record_id": "approved-1",
            "period_start": "2026-10-05",
            "period_end": "2026-10-11",
            "kind": "COMMISSION",
            "status": "APPROVED",
            "status_label": "Approved - Not Yet Paid",
            "basis_amount": "100.00",
            "deduction_amount": "0.00",
            "final_amount": "100.00",
        }]
        with patch(
            "core.own_contractor_payment_api.User.objects.filter"
        ) as lookup, patch(
            "core.own_contractor_payment_api.require_own_compensation_permission"
        ) as gate, patch(
            "core.own_contractor_payment_api.own_contractor_payment_disclosure",
            return_value=allowed,
        ) as disclosure:
            lookup.return_value.first.return_value = self.verified
            response = own_contractor_payment_history(
                self.request(user=self.actor)
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, {"results": allowed})
            gate.assert_called_once_with(self.verified)
            disclosure.assert_called_once_with(self.verified)

    def test_empty_history_returns_no_records(self):
        with patch(
            "core.own_contractor_payment_api.User.objects.filter"
        ) as lookup, patch(
            "core.own_contractor_payment_api.require_own_compensation_permission"
        ), patch(
            "core.own_contractor_payment_api.own_contractor_payment_disclosure",
            return_value=[],
        ):
            lookup.return_value.first.return_value = self.verified
            response = own_contractor_payment_history(
                self.request(user=self.actor)
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, {"results": []})

    def test_response_disables_private_cache(self):
        with patch(
            "core.own_contractor_payment_api.User.objects.filter"
        ) as lookup, patch(
            "core.own_contractor_payment_api.require_own_compensation_permission"
        ), patch(
            "core.own_contractor_payment_api.own_contractor_payment_disclosure",
            return_value=[],
        ):
            lookup.return_value.first.return_value = self.verified
            response = own_contractor_payment_history(
                self.request(user=self.actor)
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_post_and_patch_are_rejected_without_service_calls(self):
        with patch(
            "core.own_contractor_payment_api.User.objects.filter"
        ) as lookup, patch(
            "core.own_contractor_payment_api.own_contractor_payment_disclosure"
        ) as disclosure:
            for method in ("post", "patch"):
                with self.subTest(method=method):
                    response = own_contractor_payment_history(
                        self.request(method, user=self.actor)
                    )
                    self.assertEqual(response.status_code, 405)
            lookup.assert_not_called()
            disclosure.assert_not_called()