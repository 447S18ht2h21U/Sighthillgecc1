"""Fail-closed customer payment API acceptance tests."""
from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from .models import CustomerPayment, Role, User


class CustomerPaymentApi4714Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.comptroller = User.objects.create_user(
            username="payment_comptroller_4714",
            role=Role.COMPTROLLER,
            initials="PC",
        )
        cls.associate = User.objects.create_user(
            username="payment_associate_4714",
            role=Role.SALES_ASSOCIATE,
            initials="PA",
        )

    def setUp(self):
        self.client = APIClient()

    def test_anonymous_list_denied(self):
        response = self.client.get("/api/customer-payments/")
        self.assertIn(response.status_code, (401, 403))

    def test_associate_cannot_record_payment(self):
        self.client.force_authenticate(user=self.associate)
        response = self.client.post(
            "/api/customer-payments/",
            {
                "project": "00000000-0000-0000-0000-000000000001",
                "kind": "DEPOSIT",
                "amount": "5000.00",
                "received_date": date.today().isoformat(),
                "payment_reference": "TEST-NOT-REAL",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(CustomerPayment.objects.count(), 0)

    def test_associate_cannot_view_payments(self):
        self.client.force_authenticate(user=self.associate)
        response = self.client.get("/api/customer-payments/")
        self.assertEqual(response.status_code, 403)

    def test_invalid_payment_rejected(self):
        self.client.force_authenticate(user=self.comptroller)
        response = self.client.post(
            "/api/customer-payments/",
            {"kind": "DEPOSIT", "amount": "0.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(CustomerPayment.objects.count(), 0)

    def test_missing_payment_cannot_be_bank_confirmed(self):
        self.client.force_authenticate(user=self.comptroller)
        response = self.client.post(
            "/api/customer-payments/00000000-0000-0000-0000-000000000001/bank-confirm/",
            {
                "bank_reference": "TEST-ONLY",
                "confirmation_date": date.today().isoformat(),
                "confirmation_method": "TEST",
                "confirmation_note": "No payment exists",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(CustomerPayment.objects.count(), 0)
