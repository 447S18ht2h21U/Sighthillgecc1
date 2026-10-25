"""Security tests for CEO payment exceptions."""

from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .ceo_payment_exception_services import (
    request_payment_exception,
    decide_payment_exception,
    revoke_payment_exception,
    has_valid_payment_exception,
)
from .models import (
    AuditEvent,
    CEOPaymentException,
    Customer,
    MSR,
    Project,
    Role,
    User,
)


class CEOPaymentExceptionSecurityTests(TestCase):

    def setUp(self):
        self.sales = User.objects.create_user(
            username="payment_exception_sales",
            role=Role.SALES_ASSOCIATE,
            initials="SA",
        )
        self.manager = User.objects.create_user(
            username="payment_exception_manager",
            role=Role.SALES_MANAGER,
            initials="SM",
        )
        self.ceo = User.objects.create_user(
            username="payment_exception_ceo",
            role=Role.CEO,
            initials="CE",
        )
        self.customer = Customer.objects.create(
            legal_name="Payment Exception Test Customer",
            billing_address="1 Test Street",
            created_by=self.sales,
        )
        self.project = Project.objects.create(
            code="PAYMENT-EXCEPTION-TEST",
            customer=self.customer,
            location="1 Installation Street",
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
                "payment_option": "100_PERCENT_COMPLETION",
                "financing_type": "NON_FINANCED",
                "total_price": "1000.00",
            },
        )
        self.project.current_approved = self.msr
        self.project.save(update_fields=["current_approved"])

    def request(self):
        return request_payment_exception(
            actor=self.sales,
            project_id=self.project.pk,
            msr_id=self.msr.pk,
            reason="Customer requests payment after installation.",
        )

    def test_standard_deposit_msr_cannot_request_exception(self):
        deposit_msr = MSR.objects.create(
            project=self.project,
            number=2,
            created_by=self.sales,
            prepared_by=self.sales,
            status="APPROVED",
            snapshot={
                "payment_option": "50_PERCENT_DEPOSIT",
                "financing_type": "NON_FINANCED",
                "total_price": "1000.00",
            },
        )
        self.project.current_approved = deposit_msr
        self.project.save(update_fields=["current_approved"])

        with self.assertRaises(ValidationError) as captured:
            request_payment_exception(
                actor=self.sales,
                project_id=self.project.pk,
                msr_id=deposit_msr.pk,
                reason="Customer requests payment after installation.",
            )

        self.assertIn(
            "100% payment after completion",
            str(captured.exception),
        )
        self.assertFalse(
            CEOPaymentException.objects.filter(msr=deposit_msr).exists()
        )
        self.assertFalse(
            AuditEvent.objects.filter(
                action="CEO_PAYMENT_EXCEPTION_REQUESTED"
            ).exists()
        )
    def test_pending_request_is_not_valid(self):
        self.request()
        self.assertFalse(
            has_valid_payment_exception(self.project, self.msr)
        )

    def test_sales_cannot_approve(self):
        exception = self.request()
        with self.assertRaises(PermissionDenied):
            decide_payment_exception(
                actor=self.sales,
                exception_id=exception.pk,
                approve=True,
                reason="Not authorized.",
            )

    def test_ceo_approval_requires_written_reason(self):
        exception = self.request()
        with self.assertRaises(ValidationError):
            decide_payment_exception(
                actor=self.ceo,
                exception_id=exception.pk,
                approve=True,
                reason="   ",
            )

    def test_ceo_approval_creates_valid_exception(self):
        exception = self.request()
        approved = decide_payment_exception(
            actor=self.ceo,
            exception_id=exception.pk,
            approve=True,
            reason="CEO approves this specific payment exception.",
        )
        self.assertEqual(
            approved.status,
            CEOPaymentException.Status.APPROVED,
        )
        self.assertTrue(
            has_valid_payment_exception(self.project, self.msr)
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action="CEO_PAYMENT_EXCEPTION_APPROVED",
                entity_id=exception.pk,
            ).exists()
        )

    def test_revocation_removes_eligibility(self):
        exception = self.request()
        decide_payment_exception(
            actor=self.ceo,
            exception_id=exception.pk,
            approve=True,
            reason="Approved.",
        )
        revoke_payment_exception(
            actor=self.ceo,
            exception_id=exception.pk,
            reason="Approval withdrawn.",
        )
        self.assertFalse(
            has_valid_payment_exception(self.project, self.msr)
        )

    def test_exception_does_not_transfer_to_new_msr(self):
        exception = self.request()
        decide_payment_exception(
            actor=self.ceo,
            exception_id=exception.pk,
            approve=True,
            reason="Approved for version one.",
        )

        replacement = MSR.objects.create(
            project=self.project,
            number=2,
            created_by=self.sales,
            prepared_by=self.sales,
            status="APPROVED",
            snapshot=dict(self.msr.snapshot),
        )
        self.project.current_approved = replacement
        self.project.save(update_fields=["current_approved"])

        self.assertFalse(
            has_valid_payment_exception(self.project, replacement)
        )
        self.assertFalse(
            has_valid_payment_exception(self.project, self.msr)
        )

    def test_failed_request_audit_rolls_back(self):
        with patch(
            "core.ceo_payment_exception_services.audit",
            side_effect=RuntimeError("Audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.request()

        self.assertFalse(
            CEOPaymentException.objects.filter(msr=self.msr).exists()
        )

    def test_failed_revocation_audit_rolls_back(self):
        exception = self.request()
        decide_payment_exception(
            actor=self.ceo,
            exception_id=exception.pk,
            approve=True,
            reason="Approved for this MSR.",
        )

        with patch(
            "core.ceo_payment_exception_services.audit",
            side_effect=RuntimeError("Audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                revoke_payment_exception(
                    actor=self.ceo,
                    exception_id=exception.pk,
                    reason="Withdraw approval.",
                )

        exception.refresh_from_db()
        self.assertEqual(
            exception.status,
            CEOPaymentException.Status.APPROVED,
        )
        self.assertIsNone(exception.revoked_at)
        self.assertTrue(
            has_valid_payment_exception(self.project, self.msr)
        )
    def test_failed_approval_audit_rolls_back(self):
        exception = self.request()

        with patch(
            "core.ceo_payment_exception_services.audit",
            side_effect=RuntimeError("Audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                decide_payment_exception(
                    actor=self.ceo,
                    exception_id=exception.pk,
                    approve=True,
                    reason="CEO approved.",
                )

        exception.refresh_from_db()
        self.assertEqual(
            exception.status,
            CEOPaymentException.Status.REQUESTED,
        )
        self.assertFalse(
            has_valid_payment_exception(self.project, self.msr)
        )