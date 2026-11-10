from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .installation_eligibility import verified_signature_time
from .models import CustomerSignatureEvidence
from .rules import EASTERN
from .test_installation_schedule import InstallationScheduleTests


class CustomerSignatureIdentity4566Tests(TestCase):
    setUp = InstallationScheduleTests.setUp

    def add_signature(self, role, digest_character):
        return CustomerSignatureEvidence.objects.create(
            msr=self.project.pending,
            document_kind=CustomerSignatureEvidence.DocumentKind.CONTRACT,
            signer_role=role,
            signer_name="Fictional GECC Signer",
            signer_email="fictional@example.invalid",
            signed_at=timezone.now(),
            provider_reference="FICTIONAL-IDENTITY-GUARD-" + digest_character,
            digest=digest_character * 64,
        )

    def test_gecc_signature_cannot_satisfy_customer_contract(self):
        self.add_signature(
            CustomerSignatureEvidence.SignerRole.GECC, "a"
        )
        with self.assertRaises(ValidationError):
            verified_signature_time(
                self.project.pending,
                CustomerSignatureEvidence.DocumentKind.CONTRACT,
            )

    def test_verified_customer_signature_satisfies_customer_lookup(self):
        self.add_signature(
            CustomerSignatureEvidence.SignerRole.GECC, "b"
        )
        customer_evidence = self.add_signature(
            CustomerSignatureEvidence.SignerRole.CUSTOMER, "c"
        )
        actual = verified_signature_time(
            self.project.pending,
            CustomerSignatureEvidence.DocumentKind.CONTRACT,
        )
        self.assertEqual(
            actual, customer_evidence.signed_at.astimezone(EASTERN)
        )

    def test_invoice_signature_does_not_replace_contract_signature(self):
        CustomerSignatureEvidence.objects.create(
            msr=self.project.pending,
            document_kind=CustomerSignatureEvidence.DocumentKind.INVOICE,
            signer_role=CustomerSignatureEvidence.SignerRole.CUSTOMER,
            signer_name="Fictional Customer",
            signer_email="customer@example.invalid",
            signed_at=timezone.now(),
            provider_reference="FICTIONAL-INVOICE-IDENTITY-GUARD",
            digest="d" * 64,
        )
        with self.assertRaises(ValidationError):
            verified_signature_time(
                self.project.pending,
                CustomerSignatureEvidence.DocumentKind.CONTRACT,
            )
