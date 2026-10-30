"""Required contractor payment authorization boundaries."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .contractor_payment_services import (
    approve_contractor_payment_record,
    create_contractor_payment_record,
    mark_contractor_payment_paid,
)
from .models import (
    Contractor,
    ContractorCompensationPlan,
    ContractorEngagement,
    ContractorPaymentRecord,
    Role,
    User,
)


class ContractorPaymentAuthorizationTests(TestCase):
    def setUp(self):
        self.ceo = User.objects.create_user(
            username="contractor_auth_ceo",
            role=Role.CEO,
        )
        self.comptroller = User.objects.create_user(
            username="contractor_auth_comptroller",
            role=Role.COMPTROLLER,
        )
        self.manager = User.objects.create_user(
            username="contractor_auth_manager",
            role=Role.SALES_MANAGER,
        )
        self.technician = User.objects.create_user(
            username="contractor_auth_technician",
            role=Role.TECHNICIAN,
        )
        self.contractor = Contractor.objects.create(
            contractor_number="CTR-AUTH-001",
            legal_name="Authorization Test Contractor",
            created_by=self.comptroller,
        )
        self.engagement = ContractorEngagement.objects.create(
            contractor=self.contractor,
            engagement_code="ENG-AUTH-001",
            role_description="Installation Contractor",
            status=ContractorEngagement.Status.ACTIVE,
            start_date=date(2026, 10, 1),
            created_by=self.comptroller,
        )
        self.plan = ContractorCompensationPlan.objects.create(
            engagement=self.engagement,
            version=1,
            effective_date=date(2026, 10, 1),
            compensation_terms={"amount": "500.00"},
            status=ContractorCompensationPlan.Status.APPROVED,
            created_by=self.comptroller,
            approved_by=self.comptroller,
        )

    def make_payment(self, actor=None):
        return create_contractor_payment_record(
            actor or self.comptroller,
            self.engagement,
            self.plan,
            ContractorPaymentRecord.Kind.FIXED_COMPENSATION,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal("500.00"),
            Decimal("0.00"),
            Decimal("500.00"),
            {"source": "AUTHORIZATION_TEST"},
        )

    def test_comptroller_may_create_draft(self):
        record = self.make_payment()
        self.assertEqual(record.status, ContractorPaymentRecord.Status.DRAFT)

    def test_technician_cannot_create_draft(self):
        with self.assertRaises(PermissionDenied):
            self.make_payment(self.technician)

    def test_ceo_may_approve_draft(self):
        record = self.make_payment()
        approve_contractor_payment_record(self.ceo, record.pk)
        record.refresh_from_db()
        self.assertEqual(record.status, ContractorPaymentRecord.Status.APPROVED)
        self.assertEqual(record.approved_by_id, self.ceo.pk)

    def test_sales_manager_cannot_approve_payment(self):
        record = self.make_payment()
        with self.assertRaises(PermissionDenied):
            approve_contractor_payment_record(self.manager, record.pk)

    def test_comptroller_cannot_approve_payment(self):
        record = self.make_payment()
        with self.assertRaises(PermissionDenied):
            approve_contractor_payment_record(self.comptroller, record.pk)

    def test_disabled_ceo_cannot_approve_payment(self):
        record = self.make_payment()
        self.ceo.is_active = False
        self.ceo.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            approve_contractor_payment_record(self.ceo, record.pk)

    def test_stale_ceo_role_cannot_approve_payment(self):
        record = self.make_payment()
        stale = User.objects.get(pk=self.ceo.pk)
        User.objects.filter(pk=self.ceo.pk).update(role=Role.TECHNICIAN)
        with self.assertRaises(PermissionDenied):
            approve_contractor_payment_record(stale, record.pk)

    def test_comptroller_may_mark_ceo_approved_payment_paid(self):
        from django.utils import timezone
        from .contractor_payment_issuance_services import issue_contractor_payment
        from .contractor_payment_settlement_services import (
            verify_contractor_payment_settlement,
        )

        record = self.make_payment()
        approve_contractor_payment_record(self.ceo, record.pk)

        issuance = issue_contractor_payment(
            self.ceo,
            record.pk,
            record.final_amount,
            "ACH",
            "AUTH-TEST-CEO-ISSUANCE-001",
            "Authorization test issuance evidence",
        )

        verification = verify_contractor_payment_settlement(
            self.comptroller,
            record.pk,
            timezone.localdate(),
            record.final_amount,
            "AUTH-TEST-BANK-SETTLEMENT-001",
        )

        self.assertEqual(issuance.issued_by_id, self.ceo.pk)
        self.assertEqual(
            verification.verified_by_id,
            self.comptroller.pk,
        )

        record.refresh_from_db()
        self.assertEqual(
            record.status,
            ContractorPaymentRecord.Status.APPROVED,
        )

        mark_contractor_payment_paid(self.comptroller, record.pk)

        record.refresh_from_db()
        self.assertEqual(
            record.status,
            ContractorPaymentRecord.Status.PAID,
        )
        self.assertIsNotNone(record.paid_at)

    def test_ceo_cannot_mark_payment_paid(self):
        record = self.make_payment()
        approve_contractor_payment_record(self.ceo, record.pk)
        with self.assertRaises(PermissionDenied):
            mark_contractor_payment_paid(self.ceo, record.pk)

    def test_disabled_comptroller_cannot_mark_payment_paid(self):
        record = self.make_payment()
        approve_contractor_payment_record(self.ceo, record.pk)
        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            mark_contractor_payment_paid(self.comptroller, record.pk)
