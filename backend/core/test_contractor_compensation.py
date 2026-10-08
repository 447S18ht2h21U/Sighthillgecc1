from datetime import date

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .models import (
    Contractor,
    ContractorCompensationPlan,
    ContractorEngagement,
    Role,
    User,
)
from .contractor_services import approve_compensation_plan


class ContractorCompensationTests(TestCase):

    def test_sales_manager_cannot_approve_compensation_plan(self):
        comptroller = User.objects.create_user(
            username='compensation_comptroller',
            password='TestPassword123!',
            role=Role.COMPTROLLER,
            initials='CC',
        )

        sales_manager = User.objects.create_user(
            username='compensation_sales_manager',
            password='TestPassword123!',
            role=Role.SALES_MANAGER,
            initials='SM',
        )

        contractor = Contractor.objects.create(
            contractor_number='CTR-COMP-001',
            legal_name='Compensation Test Contractor',
            created_by=comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='CTR-COMP-001-01',
            role_description='Sales Associate',
            created_by=comptroller,
        )

        plan = ContractorCompensationPlan.objects.create(
            engagement=engagement,
            version=1,
            effective_date=date(2026, 10, 8),
            compensation_terms={'type': 'TEST_ONLY'},
            created_by=comptroller,
        )

        with self.assertRaises(PermissionDenied):
            approve_compensation_plan(sales_manager, plan.id)

        plan.refresh_from_db()

        self.assertEqual(
            plan.status,
            ContractorCompensationPlan.Status.DRAFT,
        )

    def test_comptroller_can_approve_active_engagement_plan(self):
        comptroller = User.objects.create_user(
            username='compensation_approval_comptroller',
            password='TestPassword123!',
            role=Role.COMPTROLLER,
            initials='CA',
        )

        contractor = Contractor.objects.create(
            contractor_number='CTR-COMP-002',
            legal_name='Approved Compensation Contractor',
            created_by=comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='CTR-COMP-002-01',
            role_description='Technical Associate',
            status=ContractorEngagement.Status.ACTIVE,
            created_by=comptroller,
        )

        plan = ContractorCompensationPlan.objects.create(
            engagement=engagement,
            version=1,
            effective_date=date(2026, 10, 8),
            compensation_terms={'type': 'TEST_ONLY'},
            created_by=comptroller,
        )

        from .contractor_services import approve_compensation_plan

        approve_compensation_plan(comptroller, plan.id)

        plan.refresh_from_db()

        self.assertEqual(
            plan.status,
            ContractorCompensationPlan.Status.APPROVED,
        )
        self.assertEqual(plan.approved_by, comptroller)
        self.assertIsNotNone(plan.approved_at)

    def test_approved_compensation_terms_reject_direct_database_update(self):
        from django.db import DatabaseError, transaction

        comptroller = User.objects.create_user(
            username='compensation_immutable_comptroller',
            password='TestPassword123!',
            role=Role.COMPTROLLER,
            initials='CI',
        )

        contractor = Contractor.objects.create(
            contractor_number='CTR-COMP-003',
            legal_name='Immutable Compensation Contractor',
            created_by=comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='CTR-COMP-003-01',
            role_description='Technical Associate',
            status=ContractorEngagement.Status.ACTIVE,
            created_by=comptroller,
        )

        plan = ContractorCompensationPlan.objects.create(
            engagement=engagement,
            version=1,
            effective_date=date(2026, 10, 8),
            compensation_terms={'type': 'TEST_ONLY'},
            created_by=comptroller,
        )

        approve_compensation_plan(comptroller, plan.id)

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ContractorCompensationPlan.objects.filter(
                    pk=plan.pk
                ).update(
                    compensation_terms={'type': 'UNAUTHORIZED_CHANGE'}
                )

        plan.refresh_from_db()

        self.assertEqual(
            plan.compensation_terms,
            {'type': 'TEST_ONLY'},
        )


class ContractorCompensationEffectiveDateTests(TestCase):

    def test_selects_latest_approved_plan_effective_on_date(self):
        from .contractor_services import get_effective_compensation_plan

        comptroller = User.objects.create_user(
            username='effective_date_comptroller',
            password='TestPassword123!',
            role=Role.COMPTROLLER,
            initials='ED',
        )

        contractor = Contractor.objects.create(
            contractor_number='CTR-COMP-004',
            legal_name='Effective Date Test Contractor',
            created_by=comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='CTR-COMP-004-01',
            role_description='Sales Associate',
            status=ContractorEngagement.Status.ACTIVE,
            created_by=comptroller,
        )

        def create_plan(version, effective_date, approved):
            plan = ContractorCompensationPlan.objects.create(
                engagement=engagement,
                version=version,
                effective_date=effective_date,
                compensation_terms={'type': 'TEST_ONLY'},
                created_by=comptroller,
            )

            if approved:
                approve_compensation_plan(comptroller, plan.id)

            return plan

        version_1 = create_plan(1, date(2026, 10, 1), True)
        version_2 = create_plan(2, date(2026, 11, 1), True)
        create_plan(3, date(2026, 11, 10), False)

        october_plan = get_effective_compensation_plan(
            engagement.id,
            date(2026, 10, 15),
        )

        november_plan = get_effective_compensation_plan(
            engagement.id,
            date(2026, 11, 15),
        )

        self.assertEqual(october_plan.id, version_1.id)
        self.assertEqual(november_plan.id, version_2.id)

        self.assertIsNone(
            get_effective_compensation_plan(
                engagement.id,
                date(2026, 9, 15),
            )
        )