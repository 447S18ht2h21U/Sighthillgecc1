"""Regression tests for shared installation payment readiness."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .customer_payment_bank_confirmation_services import (
    confirm_customer_payment_bank_availability,
)
from .installation_payment_readiness import installation_payment_readiness
from .models import (
    Customer,
    CustomerPayment,
    CustomerPaymentAdjustment,
    MSR,
    Project,
    Role,
    User,
)
from .payment_services import (
    approve_customer_payment_adjustment,
    verify_customer_payment,
)


class InstallationPaymentReadinessTests(TestCase):

    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="shared_readiness_comptroller",
            role=Role.COMPTROLLER,
            initials="CP",
        )
        self.sales = User.objects.create_user(
            username="shared_readiness_sales",
            role=Role.SALES_ASSOCIATE,
            initials="SA",
        )
        self.manager = User.objects.create_user(
            username="shared_readiness_manager",
            role=Role.SALES_MANAGER,
            initials="SM",
        )
        self.customer = Customer.objects.create(
            legal_name="Shared Readiness Test Customer",
            billing_address="Test Address",
            created_by=self.sales,
        )
        self.project = Project.objects.create(
            code="SHARED-PAYMENT-READINESS",
            customer=self.customer,
            location="Test Installation Location",
            sales_associate=self.sales,
            reviewer=self.manager,
            state="APPROVED",
        )
        self.msr = MSR.objects.create(
            project=self.project,
            created_by=self.sales,
            prepared_by=self.sales,
            status="APPROVED",
            snapshot={
                "payment_option": "50_PERCENT_DEPOSIT",
                "financing_type": "FINANCED",
                "total_price": "10000.00",
            },
        )
        self.project.current_approved = self.msr
        self.project.save(update_fields=["current_approved"])

    def create_payment(self, *, amount="5000.00", reference="PAY-001"):
        payment = CustomerPayment.objects.create(
            project=self.project,
            msr=self.msr,
            kind=CustomerPayment.Kind.DEPOSIT,
            amount=Decimal(amount),
            received_date=timezone.localdate(),
            payment_reference=reference,
            recorded_by=self.comptroller,
        )
        return payment

    def verify_and_confirm(self, payment):
        verify_customer_payment(self.comptroller, payment.pk)

        return confirm_customer_payment_bank_availability(
            actor=self.comptroller,
            payment_id=payment.pk,
            bank_reference="BANK-" + payment.payment_reference,
            confirmation_date=timezone.localdate(),
            confirmation_method="Bank transaction reviewed",
            confirmation_note="Funds confirmed available.",
        )

    def refund(self, payment, amount, reference):
        adjustment = CustomerPaymentAdjustment.objects.create(
            payment=payment,
            kind=CustomerPaymentAdjustment.Kind.REFUND,
            amount=Decimal(amount),
            adjustment_date=timezone.localdate(),
            adjustment_reference=reference,
            reason="Payment-readiness regression test",
            recorded_by=self.comptroller,
        )
        approve_customer_payment_adjustment(
            self.comptroller,
            adjustment.pk,
        )
        return adjustment

    def test_no_payment_requires_deposit(self):
        result = installation_payment_readiness(self.project)
        self.assertFalse(result["payment_ready"])
        self.assertEqual(result["required_deposit"], Decimal("5000.00"))
        self.assertEqual(result["remaining_deposit"], Decimal("5000.00"))

    def test_unverified_payment_does_not_count(self):
        self.create_payment()
        result = installation_payment_readiness(self.project)
        self.assertEqual(result["qualifying_funds"], Decimal("0.00"))
        self.assertFalse(result["payment_ready"])

    def test_verified_without_bank_confirmation_does_not_count(self):
        payment = self.create_payment()
        verify_customer_payment(self.comptroller, payment.pk)
        result = installation_payment_readiness(self.project)
        self.assertEqual(result["qualifying_funds"], Decimal("0.00"))
        self.assertFalse(result["payment_ready"])

    def test_bank_confirmed_deposit_is_ready(self):
        payment = self.create_payment()
        self.verify_and_confirm(payment)
        result = installation_payment_readiness(self.project)
        self.assertTrue(result["payment_ready"])
        self.assertEqual(result["qualifying_funds"], Decimal("5000.00"))

    def test_non_financed_also_requires_deposit(self):
        snapshot = {
            **self.msr.snapshot,
            "financing_type": "NON_FINANCED",
        }
        with patch.object(self.msr, "snapshot", snapshot):
            with patch.object(
                Project,
                "current_approved",
                property(lambda instance: self.msr),
            ):
                result = installation_payment_readiness(self.project)

        self.assertFalse(result["payment_ready"])
        self.assertEqual(result["required_deposit"], Decimal("5000.00"))

    def test_partial_refund_reduces_qualifying_funds(self):
        payment = self.create_payment()
        self.verify_and_confirm(payment)
        self.refund(payment, "1000.00", "REFUND-001")

        result = installation_payment_readiness(self.project)

        self.assertFalse(result["payment_ready"])
        self.assertEqual(result["qualifying_funds"], Decimal("4000.00"))
        self.assertEqual(result["remaining_deposit"], Decimal("1000.00"))

    def test_multiple_confirmed_payments_combine(self):
        first = self.create_payment(
            amount="3000.00", reference="PAY-003"
        )
        second = self.create_payment(
            amount="2000.00", reference="PAY-004"
        )
        self.verify_and_confirm(first)
        self.verify_and_confirm(second)

        result = installation_payment_readiness(self.project)

        self.assertTrue(result["payment_ready"])
        self.assertEqual(result["qualifying_funds"], Decimal("5000.00"))

    def test_old_msr_payment_does_not_count_for_new_version(self):
        payment = self.create_payment()
        self.verify_and_confirm(payment)

        new_msr = MSR.objects.create(
            project=self.project,
            number=2,
            created_by=self.sales,
            prepared_by=self.sales,
            status="APPROVED",
            snapshot={
                "payment_option": "50_PERCENT_DEPOSIT",
                "financing_type": "FINANCED",
                "total_price": "12000.00",
            },
        )
        self.project.current_approved = new_msr
        self.project.save(update_fields=["current_approved"])

        result = installation_payment_readiness(self.project)

        self.assertFalse(result["payment_ready"])
        self.assertEqual(result["required_deposit"], Decimal("6000.00"))
        self.assertEqual(result["qualifying_funds"], Decimal("0.00"))

    def test_valid_ceo_exception_is_recognized(self):
        with patch(
            "core.installation_payment_readiness.has_valid_payment_exception",
            return_value=True,
        ):
            result = installation_payment_readiness(self.project)

        self.assertTrue(result["payment_ready"])
        self.assertTrue(result["ceo_exception_valid"])

    def test_invalid_ceo_exception_does_not_bypass_deposit(self):
        with patch(
            "core.installation_payment_readiness.has_valid_payment_exception",
            return_value=False,
        ):
            result = installation_payment_readiness(self.project)

        self.assertFalse(result["payment_ready"])

    def test_invalid_financing_classification_rejected(self):
        snapshot = {
            **self.msr.snapshot,
            "financing_type": "INVALID",
        }
        with patch.object(self.msr, "snapshot", snapshot):
            with patch.object(
                Project,
                "current_approved",
                property(lambda instance: self.msr),
            ):
                with self.assertRaises(ValidationError):
                    installation_payment_readiness(self.project)

    def test_invalid_total_price_rejected(self):
        snapshot = {
            **self.msr.snapshot,
            "total_price": "invalid",
        }
        with patch.object(self.msr, "snapshot", snapshot):
            with patch.object(
                Project,
                "current_approved",
                property(lambda instance: self.msr),
            ):
                with self.assertRaises(ValidationError):
                    installation_payment_readiness(self.project)

    def test_missing_current_approved_msr_rejected(self):
        self.project.current_approved = None

        with self.assertRaises(ValidationError):
            installation_payment_readiness(self.project)

    def approve_real_ceo_exception(self):
        from .ceo_payment_exception_services import (
            request_payment_exception,
            decide_payment_exception,
        )

        self.ceo = User.objects.create_user(
            username="shared_readiness_ceo",
            role=Role.CEO,
            initials="CE",
        )

        # A CEO exception is permitted only for an MSR
        # explicitly specifying payment after completion.
        snapshot = {
            **self.msr.snapshot,
            "payment_option": "100_PERCENT_COMPLETION",
        }

        # Construct the approved test MSR directly so its
        # immutable snapshot is not edited after approval.
        exception_msr = MSR.objects.create(
            project=self.project,
            number=2,
            created_by=self.sales,
            prepared_by=self.sales,
            status="APPROVED",
            snapshot=snapshot,
        )

        self.project.current_approved = exception_msr
        self.project.save(update_fields=["current_approved"])

        exception = request_payment_exception(
            actor=self.sales,
            project_id=self.project.pk,
            msr_id=exception_msr.pk,
            reason="Customer requests payment after installation.",
        )

        decide_payment_exception(
            actor=self.ceo,
            exception_id=exception.pk,
            approve=True,
            reason="Approved individual project payment exception.",
        )

        return exception, exception_msr

    def test_real_ceo_exception_allows_payment_readiness(self):
        exception, exception_msr = self.approve_real_ceo_exception()

        result = installation_payment_readiness(self.project)

        self.assertTrue(result["payment_ready"])
        self.assertTrue(result["ceo_exception_valid"])
        self.assertEqual(result["qualifying_funds"], Decimal("0.00"))
        self.assertEqual(result["msr_id"], str(exception_msr.pk))

    def test_revoked_ceo_exception_restores_deposit_requirement(self):
        from .ceo_payment_exception_services import revoke_payment_exception

        exception, exception_msr = self.approve_real_ceo_exception()

        revoke_payment_exception(
            actor=self.ceo,
            exception_id=exception.pk,
            reason="Payment exception withdrawn.",
        )

        result = installation_payment_readiness(self.project)

        self.assertFalse(result["payment_ready"])
        self.assertFalse(result["ceo_exception_valid"])
        self.assertEqual(result["remaining_deposit"], Decimal("5000.00"))

    def test_ceo_exception_does_not_transfer_to_new_msr(self):
        self.approve_real_ceo_exception()

        newer_msr = MSR.objects.create(
            project=self.project,
            number=3,
            created_by=self.sales,
            prepared_by=self.sales,
            status="APPROVED",
            snapshot={
                "payment_option": "50_PERCENT_DEPOSIT",
                "financing_type": "FINANCED",
                "total_price": "12000.00",
            },
        )

        self.project.current_approved = newer_msr
        self.project.save(update_fields=["current_approved"])

        result = installation_payment_readiness(self.project)

        self.assertFalse(result["payment_ready"])
        self.assertFalse(result["ceo_exception_valid"])
        self.assertEqual(result["remaining_deposit"], Decimal("6000.00"))
