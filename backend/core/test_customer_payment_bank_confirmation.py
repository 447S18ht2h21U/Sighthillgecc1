"""Security and audit tests for customer payment bank confirmations."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .customer_payment_bank_confirmation_services import (
    confirm_customer_payment_bank_availability,
)
from .models import (
    AuditEvent,
    Customer,
    CustomerPayment,
    CustomerPaymentAdjustment,
    CustomerPaymentBankConfirmation,
    MSR,
    Project,
    Role,
    User,
)
from .payment_services import verify_customer_payment


class CustomerPaymentBankConfirmationTests(TestCase):

    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="bank_confirmation_comptroller",
            role=Role.COMPTROLLER,
            initials="CP",
        )
        self.sales = User.objects.create_user(
            username="bank_confirmation_sales",
            role=Role.SALES_ASSOCIATE,
            initials="SA",
        )
        self.manager = User.objects.create_user(
            username="bank_confirmation_manager",
            role=Role.SALES_MANAGER,
            initials="SM",
        )
        self.customer = Customer.objects.create(
            legal_name="Bank Confirmation Test Customer",
            billing_address="Test Address",
            created_by=self.sales,
        )
        self.project = Project.objects.create(
            code="BANK-CONFIRMATION-TEST",
            customer=self.customer,
            location="Test Installation Address",
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
                "financing_type": "NON_FINANCED",
                "total_price": "10000.00",
            },
        )
        self.project.current_approved = self.msr
        self.project.save(update_fields=["current_approved"])

        self.payment = CustomerPayment.objects.create(
            project=self.project,
            msr=self.msr,
            kind=CustomerPayment.Kind.DEPOSIT,
            amount=Decimal("5000.00"),
            received_date=timezone.localdate(),
            payment_reference="BANK-PAYMENT-001",
            recorded_by=self.comptroller,
        )

    def confirm(self, **changes):
        values = {
            "actor": self.comptroller,
            "payment_id": self.payment.pk,
            "bank_reference": "BANK-REFERENCE-001",
            "confirmation_date": timezone.localdate(),
            "confirmation_method": "Bank transaction reviewed",
            "confirmation_note": "Funds available according to bank record.",
        }
        values.update(changes)
        return confirm_customer_payment_bank_availability(**values)

    def verify(self):
        return verify_customer_payment(
            self.comptroller,
            self.payment.pk,
        )

    def test_verified_payment_can_be_confirmed(self):
        self.verify()
        confirmation = self.confirm()

        self.assertEqual(confirmation.payment_id, self.payment.pk)
        self.assertEqual(
            confirmation.confirmed_by_id,
            self.comptroller.pk,
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action="customer.payment.bank_availability.confirmed",
                entity_id=confirmation.pk,
            ).exists()
        )

    def test_unverified_payment_rejected(self):
        with self.assertRaises(ValidationError):
            self.confirm()

        self.assertFalse(
            CustomerPaymentBankConfirmation.objects.exists()
        )

    def test_sales_associate_rejected(self):
        self.verify()

        with self.assertRaises(PermissionDenied):
            self.confirm(actor=self.sales)

    def test_inactive_comptroller_rejected(self):
        self.verify()
        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            self.confirm()

    def test_blank_bank_reference_rejected(self):
        self.verify()

        with self.assertRaises(ValidationError):
            self.confirm(bank_reference="   ")

    def test_blank_confirmation_method_rejected(self):
        self.verify()

        with self.assertRaises(ValidationError):
            self.confirm(confirmation_method=" ")

    def test_blank_explanation_rejected(self):
        self.verify()

        with self.assertRaises(ValidationError):
            self.confirm(confirmation_note=" ")

    def test_future_funds_date_rejected(self):
        self.verify()

        with self.assertRaises(ValidationError):
            self.confirm(
                confirmation_date=timezone.localdate() + timedelta(days=1)
            )

    def test_funds_date_before_receipt_rejected(self):
        self.verify()

        with self.assertRaises(ValidationError):
            self.confirm(
                confirmation_date=self.payment.received_date
                - timedelta(days=1)
            )

    def test_duplicate_confirmation_rejected(self):
        self.verify()
        self.confirm()

        with self.assertRaises(ValidationError):
            self.confirm()

        self.assertEqual(
            CustomerPaymentBankConfirmation.objects.count(),
            1,
        )

    def test_confirmation_timestamp_is_server_generated(self):
        self.verify()
        before = timezone.now()
        confirmation = self.confirm()
        after = timezone.now()

        self.assertGreaterEqual(confirmation.confirmed_at, before)
        self.assertLessEqual(confirmation.confirmed_at, after)

    def test_audit_failure_rolls_back_confirmation(self):
        self.verify()

        previous_audits = AuditEvent.objects.count()

        with patch(
            "core.customer_payment_bank_confirmation_services.audit",
            side_effect=RuntimeError("Audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.confirm()

        self.assertEqual(
            CustomerPaymentBankConfirmation.objects.count(),
            0,
        )
        self.assertEqual(
            AuditEvent.objects.count(),
            previous_audits,
        )

    def test_fully_adjusted_payment_rejected(self):
        self.verify()

        adjustment = CustomerPaymentAdjustment.objects.create(
            payment=self.payment,
            kind=CustomerPaymentAdjustment.Kind.REFUND,
            amount=Decimal("5000.00"),
            adjustment_date=timezone.localdate(),
            adjustment_reference="FULL-REFUND-001",
            reason="Full refund recorded",
            recorded_by=self.comptroller,
        )

        from .payment_services import approve_customer_payment_adjustment

        approve_customer_payment_adjustment(
            self.comptroller,
            adjustment.pk,
        )

        with self.assertRaises(ValidationError):
            self.confirm()

    def test_wrong_confirmation_date_type_rejected(self):
        self.verify()

        with self.assertRaises(ValidationError):
            self.confirm(confirmation_date="2026-10-25")

    def test_partial_refund_still_allows_confirmation(self):
        self.verify()

        from .payment_services import approve_customer_payment_adjustment

        adjustment = CustomerPaymentAdjustment.objects.create(
            payment=self.payment,
            kind=CustomerPaymentAdjustment.Kind.REFUND,
            amount=Decimal("1000.00"),
            adjustment_date=timezone.localdate(),
            adjustment_reference="PARTIAL-REFUND-001",
            reason="Partial customer refund",
            recorded_by=self.comptroller,
        )

        approve_customer_payment_adjustment(
            self.comptroller,
            adjustment.pk,
        )

        confirmation = self.confirm()

        self.assertEqual(confirmation.payment_id, self.payment.pk)
        self.assertEqual(
            CustomerPaymentBankConfirmation.objects.count(),
            1,
        )

    def test_later_refund_preserves_historical_confirmation(self):
        self.verify()
        confirmation = self.confirm()

        from .payment_services import approve_customer_payment_adjustment

        adjustment = CustomerPaymentAdjustment.objects.create(
            payment=self.payment,
            kind=CustomerPaymentAdjustment.Kind.REFUND,
            amount=Decimal("2000.00"),
            adjustment_date=timezone.localdate(),
            adjustment_reference="LATER-REFUND-001",
            reason="Refund after bank confirmation",
            recorded_by=self.comptroller,
        )

        approve_customer_payment_adjustment(
            self.comptroller,
            adjustment.pk,
        )

        confirmation.refresh_from_db()

        self.assertEqual(confirmation.payment_id, self.payment.pk)
        self.assertEqual(
            CustomerPaymentBankConfirmation.objects.count(),
            1,
        )

        self.assertEqual(
            adjustment.amount,
            Decimal("2000.00"),
        )

    def test_new_msr_preserves_historical_confirmation(self):
        self.verify()
        confirmation = self.confirm()

        new_msr = MSR.objects.create(
            project=self.project,
            number=2,
            created_by=self.sales,
            prepared_by=self.sales,
            status="APPROVED",
            snapshot={
                "payment_option": "50_PERCENT_DEPOSIT",
                "financing_type": "NON_FINANCED",
                "total_price": "12000.00",
            },
        )

        self.project.current_approved = new_msr
        self.project.save(update_fields=["current_approved"])

        confirmation.refresh_from_db()

        self.assertEqual(confirmation.payment.msr_id, self.msr.pk)
        self.assertEqual(
            CustomerPaymentBankConfirmation.objects.count(),
            1,
        )
        self.assertEqual(
            self.project.current_approved_id,
            new_msr.pk,
        )

    def test_audit_failure_preserves_head_events_and_outbox(self):
        from .models import AuditHead, Outbox

        self.verify()

        head_before = list(
            AuditHead.objects.values_list(
                "id",
                "sequence",
                "digest",
            )
        )

        events_before = list(
            AuditEvent.objects.order_by("sequence").values_list(
                "id",
                "sequence",
                "digest",
            )
        )

        outbox_before = list(
            Outbox.objects.order_by("created_at").values_list(
                "id",
                "event_id",
                "topic",
            )
        )

        with patch(
            "core.customer_payment_bank_confirmation_services.audit",
            side_effect=RuntimeError("Audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.confirm()

        self.assertFalse(
            CustomerPaymentBankConfirmation.objects.exists()
        )

        self.assertEqual(
            list(
                AuditHead.objects.values_list(
                    "id",
                    "sequence",
                    "digest",
                )
            ),
            head_before,
        )

        self.assertEqual(
            list(
                AuditEvent.objects.order_by("sequence").values_list(
                    "id",
                    "sequence",
                    "digest",
                )
            ),
            events_before,
        )

        self.assertEqual(
            list(
                Outbox.objects.order_by("created_at").values_list(
                    "id",
                    "event_id",
                    "topic",
                )
            ),
            outbox_before,
        )
