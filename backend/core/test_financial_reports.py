from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.utils import timezone

from rest_framework.exceptions import ValidationError

from .financial_report_services import (
    create_income_statement,
    approve_financial_report,
)
from .payment_services import (
    verify_customer_payment,
)
from .financial_report_services import (
    create_balance_sheet,
)
from .models import (
    MSR,
    Project,
    Customer,
	CustomerPayment,
    ProjectCostRecord,
    Contractor,
    ContractorEngagement,
    ContractorCompensationPlan,
    ContractorPaymentRecord,
    Employee,
    EmployeeCompensationPlan,
    EmployeePayrollRecord,
    CommissionRecord,
    FinancialReport,
    Role,
    User,
)
from .project_cost_services import approve_project_cost_record
from .contractor_payment_services import (
    create_contractor_payment_record,
    approve_contractor_payment_record,
    mark_contractor_payment_paid,
)
from .employee_payroll_services import (
    create_employee_payroll_record,
    approve_employee_payroll_record,
    mark_employee_payroll_paid,
)
from .commission_record_services import (
    approve_commission_record,
)


class FinancialReportTests(TestCase):

    def setUp(self):

        self.comptroller = User.objects.create_user(
            username='financial_report_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CC',
        )

        self.customer = Customer.objects.create(
            legal_name='Financial Report Customer',
            billing_address='123 Financial Road',
            created_by=self.comptroller,
        )

        self.project = Project.objects.create(
            code='FIN-REPORT-001',
            customer=self.customer,
            location='Financial Report Location',
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state='APPROVED',
        )

        self.msr = MSR.objects.create(
            project=self.project,
            number=1,
            status='APPROVED',
            snapshot={
                'total_price': '10000.00',
            },
            created_by=self.comptroller,
            prepared_by=self.comptroller,
            approved_by=self.comptroller,
            approved_at=timezone.now(),
        )

        self.project.current_approved = self.msr
        self.project.save(
            update_fields=['current_approved']
        )

        self.cost_record = ProjectCostRecord.objects.create(
            project=self.project,
            msr=self.msr,
            version=1,
            equipment_cost=Decimal('2000.00'),
            material_cost=Decimal('1000.00'),
            dealer_fee=Decimal('500.00'),
            technician_cost=Decimal('750.00'),
            lead_cost=Decimal('3000.00'),
            damon_cost=Decimal('500.00'),
            jerry_cost=Decimal('250.00'),
            created_by=self.comptroller,
        )

        approve_project_cost_record(
            self.comptroller,
            self.cost_record.id,
        )

    def create_paid_contractor_payment(self):

        contractor = Contractor.objects.create(
            contractor_number='CTR-FIN-001',
            legal_name='Financial Contractor',
            created_by=self.comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='ENG-FIN-001',
            role_description='Installer',
            start_date=date(2026, 10, 1),
            status=ContractorEngagement.Status.ACTIVE,
            created_by=self.comptroller,
        )

        plan = ContractorCompensationPlan.objects.create(
            engagement=engagement,
            version=1,
            effective_date=date(2026, 10, 1),
            compensation_terms={
                'amount': '1000.00',
            },
            status=(
                ContractorCompensationPlan.Status.APPROVED
            ),
            created_by=self.comptroller,
            approved_by=self.comptroller,
        )

        payment = create_contractor_payment_record(
            self.comptroller,
            engagement,
            plan,
            ContractorPaymentRecord.Kind.FIXED_COMPENSATION,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal('1000.00'),
            Decimal('0.00'),
            Decimal('1000.00'),
            {
                'source': 'FINANCIAL_REPORT_TEST',
            },
        )

        approve_contractor_payment_record(
            self.comptroller,
            payment.id,
        )

        mark_contractor_payment_paid(
            self.comptroller,
            payment.id,
        )

    def create_paid_employee_payroll(self):

        employee = Employee.objects.create(
            employee_number='EMP-FIN-001',
            legal_name='Financial Employee',
            hire_date=date(2026, 10, 1),
            status=Employee.Status.ACTIVE,
            created_by=self.comptroller,
        )

        plan = EmployeeCompensationPlan.objects.create(
            employee=employee,
            version=1,
            kind=EmployeeCompensationPlan.Kind.SALARY,
            effective_date=date(2026, 10, 1),
            compensation_terms={
                'salary': '60000.00',
            },
            status=(
                EmployeeCompensationPlan.Status.APPROVED
            ),
            created_by=self.comptroller,
            approved_by=self.comptroller,
        )

        payroll = create_employee_payroll_record(
            self.comptroller,
            employee,
            plan,
            EmployeePayrollRecord.Kind.SALARY,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal('2500.00'),
            Decimal('500.00'),
            Decimal('2000.00'),
            {
                'source': 'FINANCIAL_REPORT_TEST',
            },
        )

        approve_employee_payroll_record(
            self.comptroller,
            payroll.id,
        )

        mark_employee_payroll_paid(
            self.comptroller,
            payroll.id,
        )

    def create_approved_commission(self):

        commission = CommissionRecord.objects.create(
            project=self.project,
            msr=self.msr,
            kind=CommissionRecord.Kind.RYAN_VARIABLE,
            rate=Decimal('0.1500'),
            basis_amount=Decimal('3000.00'),
            deduction_amount=Decimal('0.00'),
            final_amount=Decimal('450.00'),
            calculation_snapshot={
                'source': 'FINANCIAL_REPORT_TEST',
            },
            created_by=self.comptroller,
            recipient=self.comptroller,
        )

        approve_commission_record(
            self.comptroller,
            commission.id,
        )

        return commission

    def test_income_statement_calculates_financial_results(self):

        self.create_paid_contractor_payment()

        self.create_paid_employee_payroll()

        self.create_approved_commission()

        report = create_income_statement(
            self.comptroller,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        self.assertEqual(
            report.kind,
            FinancialReport.Kind.INCOME_STATEMENT,
        )

        snapshot = report.report_snapshot

        self.assertEqual(
            snapshot['revenue'],
            '10000.00',
        )

        self.assertEqual(
            snapshot['direct_costs'],
            '8000.00',
        )

        self.assertEqual(
            snapshot['gross_profit'],
            '2000.00',
        )

        self.assertEqual(
            snapshot['contractor_expense'],
            '1000.00',
        )

        self.assertEqual(
            snapshot['employee_expense'],
            '2000.00',
        )

        self.assertEqual(
            snapshot['commission_expense'],
            '450.00',
        )

        self.assertEqual(
            snapshot['net_income'],
            '-1450.00',
        )

    def test_financial_report_can_be_approved(self):

        report = create_income_statement(
            self.comptroller,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        approved = approve_financial_report(
            self.comptroller,
            report.id,
        )

        self.assertEqual(
            approved.status,
            FinancialReport.Status.APPROVED,
        )

        self.assertEqual(
            approved.approved_by_id,
            self.comptroller.id,
        )

        self.assertIsNotNone(
            approved.approved_at,
        )

    def test_approved_financial_report_cannot_be_modified(self):
        from django.db import DatabaseError, transaction

        report = create_income_statement(
            self.comptroller,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        approve_financial_report(
            self.comptroller,
            report.id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                FinancialReport.objects.filter(
                    pk=report.id,
                ).update(
                    report_snapshot={
                        'tampered': True,
                    },
                )

        report.refresh_from_db()

        self.assertEqual(
            report.status,
            FinancialReport.Status.APPROVED,
        )

        self.assertNotEqual(
            report.report_snapshot,
            {
                'tampered': True,
            },
        )

    def test_approved_financial_report_cannot_be_deleted(self):
        from django.db import DatabaseError, transaction

        report = create_income_statement(
            self.comptroller,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        approve_financial_report(
            self.comptroller,
            report.id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                FinancialReport.objects.filter(
                    pk=report.id,
                ).delete()

        report.refresh_from_db()

        self.assertEqual(
            report.status,
            FinancialReport.Status.APPROVED,
        )

    def test_balance_sheet_calculates_assets_and_liabilities(self):

        from .models import CustomerPayment

        payment = CustomerPayment.objects.create(
            project=self.project,
            msr=self.msr,
            kind=CustomerPayment.Kind.FULL,
            amount=Decimal('10000.00'),
            received_date=date(2026, 10, 15),
            payment_reference='FIN-BS-001',
            recorded_by=self.comptroller,
        )

        verify_customer_payment(
            self.comptroller,
            payment.id,
        )
        payment.refresh_from_db()

        print(
            'BALANCE SHEET PAYMENT:',
            payment.status,
            payment.amount,
            payment.received_date,
        )
        self.create_paid_contractor_payment()

        self.create_paid_employee_payroll()

        report = create_balance_sheet(
            self.comptroller,
            date(2026, 10, 15),
        )

        self.assertEqual(
            report.kind,
            FinancialReport.Kind.BALANCE_SHEET,
        )

        snapshot = report.report_snapshot

        self.assertEqual(
            snapshot['cash'],
            '10000.00',
        )

        self.assertEqual(
            snapshot['contractor_liabilities'],
            '0.00',
        )

        self.assertEqual(
            snapshot['employee_payroll_liabilities'],
            '0.00',
        )

        self.assertEqual(
            snapshot['total_assets'],
            '10000.00',
        )
