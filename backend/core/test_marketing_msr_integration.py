"""Isolated database-backed security tests for Marketing MSR viewing.

Run only through a separately verified in-memory SQLite test setup.
Never run these against development, acceptance, or financial databases.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Customer, MSR, Project, Role, User


class MarketingMSRIntegrationTests(TestCase):
    endpoint = "/api/marketing-msrs/"

    @classmethod
    def setUpTestData(cls):
        cls.marketing = User.objects.create_user(
            username="marketing_isolated_test",
            role=Role.MARKETING,
            initials="MK",
            password="TestPasswordOnly!123",
        )
        cls.sales_one = User.objects.create_user(
            username="sales_one_isolated_test",
            role=Role.SALES_ASSOCIATE,
            initials="S1",
            password="TestPasswordOnly!123",
        )
        cls.sales_two = User.objects.create_user(
            username="sales_two_isolated_test",
            role=Role.SALES_ASSOCIATE,
            initials="S2",
            password="TestPasswordOnly!123",
        )
        cls.manager = User.objects.create_user(
            username="manager_isolated_test",
            role=Role.SALES_MANAGER,
            initials="SM",
            password="TestPasswordOnly!123",
        )
        cls.comptroller = User.objects.create_user(
            username="comptroller_isolated_test",
            role=Role.COMPTROLLER,
            initials="CP",
            password="TestPasswordOnly!123",
        )

        customer = Customer.objects.create(
            legal_name="Isolated Marketing Test Customer",
            billing_address="Test address only",
            created_by=cls.comptroller,
        )

        cls.project_one = Project.objects.create(
            code="MK-TEST-001",
            customer=customer,
            location="Test location one",
            sales_associate=cls.sales_one,
            reviewer=cls.manager,
        )
        cls.project_two = Project.objects.create(
            code="MK-TEST-002",
            customer=customer,
            location="Test location two",
            sales_associate=cls.sales_two,
            reviewer=cls.manager,
        )

        cls.msr_one = MSR.objects.create(
            project=cls.project_one,
            created_by=cls.sales_one,
            prepared_by=cls.sales_one,
            snapshot={"customer": "Marketing test one"},
        )
        cls.msr_two = MSR.objects.create(
            project=cls.project_two,
            created_by=cls.sales_two,
            prepared_by=cls.sales_two,
            snapshot={"customer": "Marketing test two"},
        )

    def setUp(self):
        self.client = APIClient()

    def login_as(self, user):
        self.client.force_authenticate(user=user)

    def test_marketing_can_list_both_sales_associates_msrs(self):
        self.login_as(self.marketing)
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {
            str(self.msr_one.pk),
            str(self.msr_two.pk),
        })

    def test_marketing_can_retrieve_both_msrs(self):
        self.login_as(self.marketing)
        for msr in (self.msr_one, self.msr_two):
            with self.subTest(msr=str(msr.pk)):
                response = self.client.get(
                    f"{self.endpoint}{msr.pk}/"
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["id"], str(msr.pk))

    def test_marketing_api_excludes_unapproved_snapshot_fields(self):
        """List and detail responses must never expose internal fields."""
        self.msr_one.snapshot = {
            "customer": "Marketing test one",
            "base_price": "25000.00",
            "discount": "500.00",
            "total_price": "24500.00",
            "gross_profit": "9000.00",
            "net_profit": "7000.00",
            "commission": "1500.00",
            "technician_cost": "800.00",
            "payroll": {"internal": True},
            "internal_secret": "fixture-only",
        }
        self.msr_one.save(update_fields=["snapshot"])

        self.login_as(self.marketing)

        list_response = self.client.get(self.endpoint)
        self.assertEqual(list_response.status_code, 200)

        entries = [
            item for item in list_response.data["results"]
            if item["id"] == str(self.msr_one.pk)
        ]
        self.assertEqual(len(entries), 1)

        detail_response = self.client.get(
            f"{self.endpoint}{self.msr_one.pk}/"
        )
        self.assertEqual(detail_response.status_code, 200)

        for returned in (entries[0], detail_response.data):
            snapshot = returned["snapshot"]

            self.assertEqual(snapshot["customer"], "Marketing test one")
            self.assertEqual(snapshot["base_price"], "25000.00")
            self.assertEqual(snapshot["discount"], "500.00")
            self.assertEqual(snapshot["total_price"], "24500.00")

            for restricted in (
                "gross_profit",
                "net_profit",
                "commission",
                "technician_cost",
                "payroll",
                "internal_secret",
            ):
                self.assertNotIn(restricted, snapshot)

        self.msr_one.refresh_from_db()
        self.assertIn("gross_profit", self.msr_one.snapshot)

    def test_other_roles_cannot_use_marketing_endpoint(self):
        for user in (
            self.sales_one,
            self.sales_two,
            self.manager,
            self.comptroller,
        ):
            with self.subTest(role=user.role):
                self.login_as(user)
                response = self.client.get(self.endpoint)
                self.assertEqual(response.status_code, 403)

    def test_unauthenticated_request_denied(self):
        response = self.client.get(self.endpoint)
        self.assertIn(response.status_code, (401, 403))

    def test_disabled_marketing_account_denied(self):
        self.login_as(self.marketing)
        User.objects.filter(pk=self.marketing.pk).update(
            is_active=False
        )
        response = self.client.get(self.endpoint)
        self.assertIn(response.status_code, (401, 403))

    def test_reassigned_marketing_account_denied(self):
        self.login_as(self.marketing)
        User.objects.filter(pk=self.marketing.pk).update(
            role=Role.TECHNICIAN
        )
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 403)

    def test_marketing_endpoint_rejects_mutations(self):
        self.login_as(self.marketing)
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    f"{self.endpoint}{self.msr_one.pk}/",
                    {"snapshot": {"tampered": True}},
                    format="json",
                )
                self.assertEqual(response.status_code, 405)

    def test_marketing_cannot_modify_existing_msr(self):
        self.login_as(self.marketing)
        response = self.client.post(
            f"/api/msrs/{self.msr_one.pk}/transition/",
            {
                "action": "edit",
                "expected_sequence": 0,
                "snapshot": {"customer": "Unauthorized change"},
            },
            format="json",
        )
        self.assertIn(response.status_code, (403, 404))
        self.msr_one.refresh_from_db()
        self.assertEqual(
            self.msr_one.snapshot,
            {"customer": "Marketing test one"},
        )

    def test_marketing_cannot_prepare_signing_review(self):
        self.login_as(self.marketing)
        response = self.client.post(
            f"/api/msrs/{self.msr_one.pk}/signing-reviews/",
            {},
            format="json",
        )
        self.assertIn(response.status_code, (403, 404))

    def test_marketing_cannot_prepare_documents(self):
        self.login_as(self.marketing)
        response = self.client.post(
            f"/api/msrs/{self.msr_one.pk}/documents/",
            {"kind": "INVOICE"},
            format="json",
        )
        self.assertIn(response.status_code, (403, 404))

    def test_marketing_cannot_manage_customers(self):
        self.login_as(self.marketing)
        response = self.client.post(
            "/api/customers/",
            {"legal_name": "Unauthorized Customer"},
            format="json",
        )
        self.assertIn(response.status_code, (403, 404))