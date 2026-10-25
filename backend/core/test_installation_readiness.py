from django.test import TestCase

from .installation_readiness import installation_readiness
from .test_installation_eligibility import InstallationEligibilityTests


class InstallationReadinessTests(TestCase):

    def setUp(self):
        fixture = InstallationEligibilityTests()
        fixture.setUp()

        self.project = fixture.project
        self.fixture = fixture

    def test_ready_project_reports_ready(self):
        self.fixture.prepare_installation_state()

        result = installation_readiness(self.project)

        self.assertTrue(result["eligible"])


    def test_missing_contract_reports_blocker(self):
        self.fixture.prepare_installation_state(
            contract=False,
        )

        result = installation_readiness(self.project)

        self.assertFalse(result["eligible"])
        self.assertIn(
            "Verified contract signature evidence is required.",
            result["blocking_reasons"],
        )


    def test_financed_project_without_deposit_reports_blocker(self):
        self.fixture.prepare_installation_state(
            financed=True,
            deposit=False,
        )

        result = installation_readiness(self.project)

        self.assertFalse(result["eligible"])
        self.assertIn(
            "Deposit required: $5,000.00. Bank-confirmed funds remaining: $0.00. Additional funds needed: $5,000.00.",
            result["blocking_reasons"],
        )


    def test_non_financed_project_without_deposit_reports_blocked(self):
        self.fixture.prepare_installation_state(
            financed=False,
            deposit=False,
        )

        result = installation_readiness(self.project)

        self.assertFalse(result["eligible"])
        self.assertFalse(result["requirements"]["deposit_verified"])
        self.assertTrue(
            any(
                "Deposit required:" in reason
                for reason in result["blocking_reasons"]
            )
        )

    def test_future_cancellation_deadline_reports_blocker(self):
        self.fixture.prepare_installation_state(cancellation_days_after_signature=12)

        result = installation_readiness(self.project)
        self.assertFalse(result["eligible"])
        self.assertFalse(result["requirements"]["cancellation_complete"])
        self.assertIn("Cancellation deadline has not expired.", result["blocking_reasons"])

    def test_approved_refund_reduces_qualifying_deposit(self):
        from datetime import date
        from decimal import Decimal
        from rest_framework.exceptions import ValidationError
        from .models import CustomerPayment, CustomerPaymentAdjustment
        from .payment_services import approve_customer_payment_adjustment
        from .installation_eligibility import ensure_installation_eligible

        msr = self.fixture.prepare_installation_state()
        payment = CustomerPayment.objects.get(project=self.project, msr=msr)
        adjustment = CustomerPaymentAdjustment.objects.create(
            payment=payment,
            kind=CustomerPaymentAdjustment.Kind.REFUND,
            amount=Decimal("1000.00"),
            adjustment_date=date(2026, 10, 20),
            adjustment_reference="READINESS-REFUND-001",
            reason="Regression test refund",
            recorded_by=self.fixture.sales_manager,
        )
        approve_customer_payment_adjustment(self.fixture.comptroller, adjustment.id)

        result = installation_readiness(self.project)
        self.assertFalse(result["eligible"])
        self.assertFalse(result["requirements"]["deposit_verified"])
        self.assertIn("Deposit required: $5,000.00. Bank-confirmed funds remaining: $4,000.00. Additional funds needed: $1,000.00.", result["blocking_reasons"])
        with self.assertRaises(ValidationError):
            ensure_installation_eligible(self.project)

    def test_invalid_financing_classification_blocks_readiness(self):
        from unittest.mock import patch
        from .models import Project

        self.fixture.prepare_installation_state()
        for financing in ("INVALID", None):
            with self.subTest(financing=financing):
                approved = self.project.current_approved
                snapshot = {**approved.snapshot, "financing_type": financing}
                with patch.object(Project, "current_approved", property(lambda project: approved)):
                    with patch.object(approved, "snapshot", snapshot):
                        result = installation_readiness(self.project)
                self.assertFalse(result["eligible"])
                self.assertFalse(result["requirements"]["deposit_verified"])
                self.assertIn("The approved Master Sales Record needs a valid financing classification.", result["blocking_reasons"])

    def test_invalid_cancellation_dates_block_readiness(self):
        from unittest.mock import patch
        from .models import ProjectEvidence

        self.fixture.prepare_installation_state()
        original_first = ProjectEvidence.objects.filter().__class__.first
        for value in ("invalid", "2026-10-20T23:59:00"):
            with self.subTest(value=value):
                def substituted_first(queryset):
                    evidence = original_first(queryset)
                    if isinstance(evidence, ProjectEvidence) and evidence.kind == "CANCELLATION_DEADLINE":
                        evidence.data = {**evidence.data, "deadline": value}
                    return evidence
                with patch.object(ProjectEvidence.objects.filter().__class__, "first", substituted_first):
                    result = installation_readiness(self.project)
                self.assertFalse(result["eligible"])
                self.assertFalse(result["requirements"]["cancellation_complete"])
                self.assertIn("Valid cancellation deadline with UTC offset is required.", result["blocking_reasons"])
