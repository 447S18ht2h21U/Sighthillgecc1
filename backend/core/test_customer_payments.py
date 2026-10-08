"""Tests for GECC customer payment verification."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    User,
    Role,
    Customer,
    Project,
    MSR,
    CustomerPayment,
    AuditEvent,
)
from .payment_services import (
    verify_customer_payment,
    get_project_payment_status,
)

class CustomerPaymentVerificationTests(TestCase):

    def setUp(self):
        self.comptroller = User.objects.create_user(
            username='payment_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CP',
        )

        self.sales_manager = User.objects.create_user(
            username='payment_manager',
            password='test-password',
            role=Role.SALES_MANAGER,
            initials='SM',
        )

        self.customer = Customer.objects.create(
    	    legal_name='Payment Test Customer',
    	    created_by=self.sales_manager,
)	

        self.project = Project.objects.create(
            code='PAYMENT-TEST-001',
            customer=self.customer,
            location='Test installation location',
            sales_associate=self.sales_manager,
            reviewer=self.comptroller,
            state='APPROVED',
        )

        self.msr = MSR.objects.create(
            project=self.project,
            number=1,
            status='APPROVED',
            snapshot={'total_price': '1000.00'},
            created_by=self.sales_manager,
            prepared_by=self.sales_manager,
            approved_by=self.comptroller,
        )

        self.project.current_approved = self.msr
        self.project.save(update_fields=['current_approved'])

        self.payment = CustomerPayment.objects.create(
            project=self.project,
            msr=self.msr,
            kind=CustomerPayment.Kind.DEPOSIT,
            amount=Decimal('500.00'),
            received_date=date(2026, 10, 8),
            payment_reference='TEST-RECEIPT-001',
            recorded_by=self.sales_manager,
        )

    def test_comptroller_can_verify_payment(self):
        verified = verify_customer_payment(
            self.comptroller,
            self.payment.id,
        )

        self.assertEqual(
            verified.status,
            CustomerPayment.Status.VERIFIED,
        )
        self.assertEqual(
            verified.verified_by_id,
            self.comptroller.id,
        )
        self.assertIsNotNone(verified.verified_at)

        self.assertTrue(
            AuditEvent.objects.filter(
                action='customer.payment.verified',
                entity_id=self.payment.id,
            ).exists()
        )

    def test_sales_manager_cannot_verify_payment(self):
        with self.assertRaises(PermissionDenied):
            verify_customer_payment(
                self.sales_manager,
                self.payment.id,
            )

        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status,
            CustomerPayment.Status.PENDING,
        )

    def test_zero_amount_is_rejected(self):
        self.payment.amount = Decimal('0.00')
        self.payment.save(update_fields=['amount'])

        with self.assertRaises(ValidationError):
            verify_customer_payment(
                self.comptroller,
                self.payment.id,
            )

    def test_wrong_msr_is_rejected(self):
        other_msr = MSR.objects.create(
            project=self.project,
            number=2,
            status='DRAFT',
            snapshot={'total_price': '2000.00'},
            created_by=self.sales_manager,
            prepared_by=self.sales_manager,
        )

        self.payment.msr = other_msr
        self.payment.save(update_fields=['msr'])

        with self.assertRaises(ValidationError):
            verify_customer_payment(
                self.comptroller,
                self.payment.id,
            )

    def test_duplicate_verified_reference_is_rejected(self):
        verify_customer_payment(
            self.comptroller,
            self.payment.id,
        )

        duplicate = CustomerPayment.objects.create(
            project=self.project,
            msr=self.msr,
            kind=CustomerPayment.Kind.FINAL,
            amount=Decimal('500.00'),
            received_date=date(2026, 10, 8),
            payment_reference='TEST-RECEIPT-001',
            recorded_by=self.sales_manager,
        )

        with self.assertRaises(ValidationError):
            verify_customer_payment(
                self.comptroller,
                duplicate.id,
            )

        duplicate.refresh_from_db()
        self.assertEqual(
            duplicate.status,
            CustomerPayment.Status.PENDING,
        )

    def test_verified_payment_cannot_be_modified(self):
        verify_customer_payment(
            self.comptroller,
            self.payment.id,
        )

        from django.db import DatabaseError

        with self.assertRaises(DatabaseError):
            CustomerPayment.objects.filter(
                pk=self.payment.id
            ).update(amount=Decimal('999.00'))

    def test_verified_payment_cannot_be_deleted(self):
        verify_customer_payment(
            self.comptroller,
            self.payment.id,
        )

        from django.db import DatabaseError

        with self.assertRaises(DatabaseError):
            CustomerPayment.objects.filter(
                pk=self.payment.id
            ).delete()

    def test_cannot_insert_preverified_payment(self):
        from django.db import DatabaseError
        from django.utils import timezone

        with self.assertRaises(DatabaseError):
            CustomerPayment.objects.create(
                project=self.project,
                msr=self.msr,
                kind=CustomerPayment.Kind.FULL,
                amount=Decimal('1000.00'),
                received_date=date(2026, 10, 8),
                payment_reference='PREVERIFIED-TEST-001',
                recorded_by=self.sales_manager,
                status=CustomerPayment.Status.VERIFIED,
                verified_by=self.comptroller,
                verified_at=timezone.now(),
            )

    def test_deposit_does_not_mean_paid_in_full(self):
        verify_customer_payment(
            self.comptroller,
            self.payment.id,
        )

        result = get_project_payment_status(
            self.project.id
        )

        self.assertEqual(
            result['approved_total'],
            Decimal('1000.00'),
        )
        self.assertEqual(
            result['verified_total'],
            Decimal('500.00'),
        )
        self.assertEqual(
            result['outstanding_balance'],
            Decimal('500.00'),
        )
        self.assertFalse(result['paid_in_full'])

    def test_deposit_plus_final_payment_means_paid_in_full(self):
        verify_customer_payment(
            self.comptroller,
            self.payment.id,
        )

        final_payment = CustomerPayment.objects.create(
            project=self.project,
            msr=self.msr,
            kind=CustomerPayment.Kind.FINAL,
            amount=Decimal('500.00'),
            received_date=date(2026, 10, 8),
            payment_reference='TEST-FINAL-002',
            recorded_by=self.sales_manager,
        )

        verify_customer_payment(
            self.comptroller,
            final_payment.id,
        )

        result = get_project_payment_status(
            self.project.id
        )

        self.assertEqual(
            result['verified_total'],
            Decimal('1000.00'),
        )
        self.assertEqual(
            result['outstanding_balance'],
            Decimal('0.00'),
        )
        self.assertTrue(result['paid_in_full'])

    def test_pending_payment_does_not_count_toward_balance(self):
        verify_customer_payment(
            self.comptroller,
            self.payment.id,
        )

        CustomerPayment.objects.create(
            project=self.project,
            msr=self.msr,
            kind=CustomerPayment.Kind.FINAL,
            amount=Decimal('500.00'),
            received_date=date(2026, 10, 8),
            payment_reference='TEST-PENDING-003',
            recorded_by=self.sales_manager,
        )

        result = get_project_payment_status(
            self.project.id
        )

        self.assertEqual(
            result['verified_total'],
            Decimal('500.00'),
        )
        self.assertEqual(
            result['outstanding_balance'],
            Decimal('500.00'),
        )
        self.assertFalse(result['paid_in_full'])

    def test_single_full_payment_means_paid_in_full(self):
        self.payment.kind = CustomerPayment.Kind.FULL
        self.payment.amount = Decimal('1000.00')
        self.payment.save(update_fields=['kind', 'amount'])

        verify_customer_payment(
            self.comptroller,
            self.payment.id,
        )

        result = get_project_payment_status(
            self.project.id
        )

        self.assertEqual(
            result['approved_total'],
            Decimal('1000.00'),
        )
        self.assertEqual(
            result['verified_total'],
            Decimal('1000.00'),
        )
        self.assertEqual(
            result['outstanding_balance'],
            Decimal('0.00'),
        )
        self.assertTrue(result['paid_in_full'])