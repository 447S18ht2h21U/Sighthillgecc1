from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .commercial_signature_trust_5512 import (
    require_authenticated_commercial_signature,
)


class CommercialSignatureTrustBoundaryTests(SimpleTestCase):
    def test_missing_evidence_is_rejected(self):
        with self.assertRaises(ValidationError):
            require_authenticated_commercial_signature(evidence=None)

    def test_synthetic_evidence_is_rejected(self):
        with self.assertRaises(ValidationError):
            require_authenticated_commercial_signature(
                evidence={
                    "provider_reference": "DEMO-CONTRACT",
                    "signature_verified": True,
                }
            )

    def test_provider_shaped_metadata_is_rejected(self):
        with self.assertRaises(ValidationError):
            require_authenticated_commercial_signature(
                evidence={
                    "provider_status": "completed",
                    "provider_authenticated": True,
                    "signature_verified": True,
                }
            )

    def test_arbitrary_object_is_rejected(self):
        with self.assertRaises(ValidationError):
            require_authenticated_commercial_signature(
                evidence=object()
            )


class CommercialSignatureIntegrationTests(SimpleTestCase):
    def test_eligibility_rejects_legacy_signature_record(self):
        from unittest.mock import Mock, patch
        from .installation_eligibility import verified_signature_time

        record = Mock()
        record.provider_reference = "DEMO-CONTRACT"
        with patch(
            "core.installation_eligibility.CustomerSignatureEvidence.objects.filter"
        ) as query:
            query.return_value.order_by.return_value.first.return_value = record
            with self.assertRaises(ValidationError):
                verified_signature_time(
                    Mock(),
                    "CONTRACT",
                )

    def test_readiness_rejects_stored_untrusted_signatures(self):
        from unittest.mock import Mock, patch
        from .installation_readiness import installation_readiness

        from datetime import timedelta
        from django.utils import timezone

        project = Mock()
        project.current_approved.status = "APPROVED"
        record = Mock()
        record.signed_at = timezone.now() - timedelta(days=10)

        with patch(
            "core.installation_readiness.CustomerSignatureEvidence.objects.filter"
        ) as signatures, patch(
            "core.installation_readiness.ProjectEvidence.objects.filter"
        ) as deadlines, patch(
            "core.installation_payment_readiness.installation_payment_readiness"
        ) as payments:
            signatures.return_value.order_by.return_value.first.return_value = record
            deadlines.return_value.order_by.return_value.first.return_value = None
            payments.return_value = {
                "payment_ready": False,
                "explanation": "Deposit unverified."
            }
            result = installation_readiness(project)

        self.assertFalse(result["eligible"])
        self.assertFalse(result["requirements"]["contract_signed"])
        self.assertFalse(result["requirements"]["invoice_signed"])
        self.assertFalse(result["requirements"]["waiting_period_complete"])
        self.assertTrue(any(
            "Authenticated DocuSign contract" in reason
            for reason in result["blocking_reasons"]
        ))
        self.assertTrue(any(
            "Authenticated DocuSign invoice" in reason
            for reason in result["blocking_reasons"]
        ))
