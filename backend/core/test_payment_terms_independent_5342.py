"""Independent payment arrangement regression."""
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .documents import customer_payment_option_label, field_values
from .services import validate_snapshot


class IndependentPaymentTerms5342(SimpleTestCase):
    def test_standard_options_independent_of_financing(self):
        for financing in ("FINANCED", "NON_FINANCED"):
            for option in ("50_PERCENT_DEPOSIT", "100_PERCENT_COMPLETION"):
                with self.subTest(financing=financing, option=option):
                    result = validate_snapshot({
                        "financing_type": financing,
                        "payment_option": option,
                        "payment_terms": "Fictional terms",
                    })
                    self.assertEqual(result["payment_option"], option)

    def test_custom_terms_saved_in_draft(self):
        result = validate_snapshot({
            "financing_type": "NON_FINANCED",
            "payment_option": "OTHER_APPROVAL_REQUIRED",
            "payment_terms": "Fictional special terms",
        })
        self.assertEqual(
            result["payment_terms"], "Fictional special terms"
        )

    def test_custom_submission_rejected(self):
        with self.assertRaises(ValidationError):
            validate_snapshot({
                "payment_option": "OTHER_APPROVAL_REQUIRED",
                "payment_terms": "Fictional special terms",
            }, complete=True)

    def test_unknown_payment_code_rejected(self):
        with self.assertRaises(ValidationError):
            validate_snapshot({"payment_option": "UNRECOGNIZED"})

    def test_document_label_distinguishes_other(self):
        self.assertEqual(
            customer_payment_option_label({
                "payment_option": "OTHER_APPROVAL_REQUIRED"
            }),
            "Other - approval required"
        )

    def test_financed_contract_can_use_completion_payment(self):
        record = SimpleNamespace(
            snapshot={
                "customer": "Fictional Customer",
                "project_location": "123 Test Street",
                "financing_type": "FINANCED",
                "payment_option": "100_PERCENT_COMPLETION",
            },
            project=SimpleNamespace(code="TEST-5342"),
            number=1,
        )
        values = field_values("CONTRACT", record, timezone.now())
        self.assertEqual(
            values["payment_option"], "100% upon completion"
        )
        self.assertEqual(values["financing_type"], "Financed")
