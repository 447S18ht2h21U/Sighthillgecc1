"""Security regression tests for VERIDIAN Contractor Directory API."""

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Contractor, ContractorEngagement, Role, User


class ContractorDirectoryAPITests(TestCase):
    endpoint = "/api/contractors/"

    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="contractor_directory_comptroller",
            password="test-only",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.ceo = User.objects.create_user(
            username="contractor_directory_ceo",
            password="test-only",
            role=Role.CEO,
            initials="CEO",
        )
        self.sales_manager = User.objects.create_user(
            username="contractor_directory_sales_manager",
            password="test-only",
            role=Role.SALES_MANAGER,
            initials="SM",
        )

        self.contractor = Contractor.objects.create(
            contractor_number="CTR-DIR-001",
            legal_name="Directory Test Contractor",
            email="directory-test@example.com",
            phone="555-0100",
            mailing_address="Confidential Test Address",
            created_by=self.comptroller,
        )

        self.original_engagement = ContractorEngagement.objects.create(
            contractor=self.contractor,
            engagement_code="CTR-DIR-001-01",
            role_description="Technical Associate",
            status=ContractorEngagement.Status.INACTIVE,
            created_by=self.comptroller,
        )

        self.return_engagement = ContractorEngagement.objects.create(
            contractor=self.contractor,
            engagement_code="CTR-DIR-001-R01",
            role_description="Technical Associate",
            status=ContractorEngagement.Status.ACTIVE,
            created_by=self.comptroller,
        )

        self.client = APIClient()

    def test_unauthenticated_user_denied(self):
        response = self.client.get(self.endpoint)
        self.assertIn(response.status_code, (401, 403))

    def test_sales_manager_denied(self):
        self.client.force_authenticate(user=self.sales_manager)
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 403)

    def test_comptroller_can_view_directory(self):
        self.client.force_authenticate(user=self.comptroller)
        response = self.client.get(self.endpoint)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["contractor_number"],
            "CTR-DIR-001",
        )

    def test_ceo_can_view_directory(self):
        self.client.force_authenticate(user=self.ceo)
        response = self.client.get(self.endpoint)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_directory_preserves_engagement_history(self):
        self.client.force_authenticate(user=self.comptroller)
        response = self.client.get(self.endpoint)

        self.assertEqual(response.status_code, 200)

        engagements = response.data["results"][0]["engagements"]
        codes = {item["engagement_code"] for item in engagements}

        self.assertEqual(
            codes,
            {"CTR-DIR-001-01", "CTR-DIR-001-R01"},
        )

    def test_directory_excludes_private_information(self):
        self.client.force_authenticate(user=self.comptroller)
        response = self.client.get(self.endpoint)

        self.assertEqual(response.status_code, 200)

        record = response.data["results"][0]

        for field in (
            "email",
            "phone",
            "mailing_address",
            "user",
            "storage_reference",
            "compensation_terms",
            "payment_amount",
        ):
            self.assertNotIn(field, record)

    def test_directory_is_read_only(self):
        self.client.force_authenticate(user=self.comptroller)

        response = self.client.post(
            self.endpoint,
            {"contractor_number": "CTR-UNAUTHORIZED"},
            format="json",
        )

        self.assertEqual(response.status_code, 405)
        self.assertEqual(Contractor.objects.count(), 1)

    def test_inactive_user_denied(self):
        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])

        self.client.force_authenticate(user=self.comptroller)
        response = self.client.get(self.endpoint)

        self.assertIn(response.status_code, (401, 403))