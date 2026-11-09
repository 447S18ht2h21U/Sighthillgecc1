"""Real Django account tests of unregistered tax draft validation."""
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import Role, User
from .tax_draft_validation_4437Q import validate_tax_draft

class TaxDraftValidation4437QTests(TestCase):
    def setUp(self):
        self.comp = User.objects.create_user(username="tax_draft_comp_4437q", password="fixture-only", role=Role.COMPTROLLER)
        self.ceo = User.objects.create_user(username="tax_draft_ceo_4437q", password="fixture-only", role=Role.CEO)
        self.entry = dict(tax_year="2025", accounting_period="2026-10", jurisdiction="MARYLAND", tax_category="PROJECT_TAX_REVIEW", accounting_classification="OTHER_BUSINESS_TAX_EXPENSE", amount="125.00", source_reference="FICTIONAL-SOURCE", evidence_reference="FICTIONAL-EVIDENCE", explanation="FICTIONAL REVIEW", filing_status="NOT_ESTABLISHED", project_related=True, project_id="PROJECT-TEST", approved_msr_id="MSR-TEST", approved_msr_version=2, billing_address="FICTIONAL DE", installation_address="FICTIONAL MD")

    def test_01_valid_draft_does_not_post(self):
        result = validate_tax_draft(self.comp, self.entry)
        self.assertEqual(result["status"], "DRAFT_VALIDATED_ONLY")
        self.assertFalse(result["eligible_for_financial_reporting"])
        self.assertEqual(result["amount"], "125.00")

    def test_02_unauthorized_preparer_rejected(self):
        with self.assertRaises(PermissionDenied):
            validate_tax_draft(self.ceo, self.entry)

    def test_03_inactive_preparer_rejected(self):
        self.comp.is_active = False
        self.comp.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            validate_tax_draft(self.comp, self.entry)

    def test_04_required_evidence_rejected_when_missing(self):
        for field in ("source_reference", "evidence_reference", "explanation"):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    validate_tax_draft(self.comp, dict(self.entry, **{field: ""}))

    def test_05_invalid_amounts_rejected(self):
        for value in ("0", "-5.00", "NaN", "Infinity", "1.001", "nonsense"):
            with self.subTest(amount=value):
                with self.assertRaises(ValidationError):
                    validate_tax_draft(self.comp, dict(self.entry, amount=value))

    def test_06_tax_year_and_accounting_period_remain_distinct(self):
        result = validate_tax_draft(self.comp, self.entry)
        self.assertEqual(result["tax_year"], "2025")
        self.assertEqual(result["accounting_period"], "2026-10")

    def test_07_invalid_accounting_period_denied(self):
        with self.assertRaises(ValidationError):
            validate_tax_draft(self.comp, dict(self.entry, accounting_period="2026-13"))

    def test_08_project_msr_version_required(self):
        for value in (0, None, "2"):
            with self.subTest(version=value):
                with self.assertRaises(ValidationError):
                    validate_tax_draft(self.comp, dict(self.entry, approved_msr_version=value))

    def test_09_due_date_is_optional_but_must_be_real(self):
        self.assertEqual(validate_tax_draft(self.comp, self.entry)["status"], "DRAFT_VALIDATED_ONLY")
        with self.assertRaises(ValidationError):
            validate_tax_draft(self.comp, dict(self.entry, tax_due_date="2026-02-30"))

    def test_10_filing_claim_and_forged_status_denied(self):
        for changes in (dict(filing_status="FILED"), dict(status="APPROVED")):
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError):
                    validate_tax_draft(self.comp, dict(self.entry, **changes))

    def test_11_unsupported_classification_rejected(self):
        with self.assertRaises(ValidationError):
            validate_tax_draft(self.comp, dict(self.entry, accounting_classification="UNKNOWN"))

    def test_12_original_data_is_not_modified(self):
        original = dict(self.entry)
        result = validate_tax_draft(self.comp, self.entry)
        result["amount"] = "999.00"
        self.assertEqual(self.entry, original)

    def test_13_delivery_address_must_be_text(self):
        for value in (["FORGED"], {"address": "FORGED"}, 123):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_tax_draft(
                        self.comp, dict(self.entry, delivery_address=value)
                    )

    def test_14_delivery_address_cannot_be_blank_or_oversized(self):
        for value in ("   ", "X" * 2001):
            with self.subTest(length=len(value)):
                with self.assertRaises(ValidationError):
                    validate_tax_draft(
                        self.comp, dict(self.entry, delivery_address=value)
                    )

    def test_15_valid_optional_delivery_address_preserved(self):
        address = "Synthetic delivery location"
        result = validate_tax_draft(
            self.comp, dict(self.entry, delivery_address=address)
        )
        self.assertEqual(result["delivery_address"], address)
        self.assertFalse(result["eligible_for_financial_reporting"])
