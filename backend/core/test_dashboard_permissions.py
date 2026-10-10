from datetime import date

from django.test import TestCase

from .models import (
    User,
    Role,
    Customer,
    Project,
    ProjectTechnicalAssignment,
)

from .dashboard_services import (
    get_dashboard_projects,
)

from .technical_assignment_services import (
    create_technical_assignment,
)


class DashboardPermissionTests(TestCase):

    def setUp(self):

        self.sales_one = User.objects.create_user(
            username='sales_one',
            password='test-password',
            role=Role.SALES_ASSOCIATE,
            initials='S1',
        )

        self.sales_manager = User.objects.create_user(
            username='sales_manager_dashboard',
            password='test-password',
            role=Role.SALES_MANAGER,
            initials='SM',
        )

        self.sales_two = User.objects.create_user(
            username='sales_two',
            password='test-password',
            role=Role.SALES_ASSOCIATE,
            initials='S2',
        )

        self.technician = User.objects.create_user(
            username='technician_dashboard',
            password='test-password',
            role=Role.TECHNICIAN,
            initials='TC',
        )

        self.installation_manager = User.objects.create_user(
            username='installation_manager_dashboard',
            password='test-password',
            role=Role.INSTALLATION_MANAGER,
            initials='IM',
        )

        self.comptroller = User.objects.create_user(
            username='dashboard_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CP',
        )

        self.customer_one = Customer.objects.create(
            legal_name='Dashboard Customer One',
            created_by=self.sales_one,
        )

        self.customer_two = Customer.objects.create(
            legal_name='Dashboard Customer Two',
            created_by=self.sales_two,
        )

        self.project_one = Project.objects.create(
            code='DASH-PERM-001',
            customer=self.customer_one,
            location='Location One',
            sales_associate=self.sales_one,
            reviewer=self.comptroller,
        )

        self.project_two = Project.objects.create(
            code='DASH-PERM-002',
            customer=self.customer_two,
            location='Location Two',
            sales_associate=self.sales_two,
            reviewer=self.comptroller,
        )

    def test_sales_associate_only_sees_assigned_projects(self):

        dashboard = get_dashboard_projects(
            self.sales_one,
        )

        visible_projects = [
            project
            for projects in dashboard.values()
            for project in projects
        ]

        self.assertIn(
            self.project_one,
            visible_projects,
        )

        self.assertNotIn(
            self.project_two,
            visible_projects,
        )

    def test_technical_associate_only_sees_assigned_projects(self):

        create_technical_assignment(
            self.installation_manager,
            self.project_one,
            self.technician,
            date(2026, 10, 10),
        )

        dashboard = get_dashboard_projects(
            self.technician,
        )

        visible_projects = [
            project
            for projects in dashboard.values()
            for project in projects
        ]

        self.assertIn(
            self.project_one,
            visible_projects,
        )

        self.assertNotIn(
            self.project_two,
            visible_projects,
        )

    def test_comptroller_sees_all_projects(self):

        dashboard = get_dashboard_projects(
            self.comptroller,
        )

        visible_projects = [
            project
            for projects in dashboard.values()
            for project in projects
        ]

        self.assertIn(
            self.project_one,
            visible_projects,
        )

        self.assertIn(
            self.project_two,
            visible_projects,
        )

    def test_sales_manager_sees_all_projects(self):

        dashboard = get_dashboard_projects(
            self.sales_manager,
        )

        visible_projects = [
            project
            for projects in dashboard.values()
            for project in projects
        ]

        self.assertIn(
            self.project_one,
            visible_projects,
        )

        self.assertIn(
            self.project_two,
            visible_projects,
        )

    def test_installation_manager_sees_all_projects(self):

        dashboard = get_dashboard_projects(
            self.installation_manager,
        )

        visible_projects = [
            project
            for projects in dashboard.values()
            for project in projects
        ]

        self.assertIn(
            self.project_one,
            visible_projects,
        )

        self.assertIn(
            self.project_two,
            visible_projects,
        )

    