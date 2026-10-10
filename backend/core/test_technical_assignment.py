from datetime import date

from django.test import TestCase

from .models import (
    User,
    Role,
    Customer,
    Project,
    ProjectTechnicalAssignment,
)

from .technical_assignment_services import (
    create_technical_assignment,
    end_technical_assignment,
)


class TechnicalAssignmentTests(TestCase):

    def setUp(self):

        self.comptroller = User.objects.create_user(
            username='technical_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CP',
        )

        self.installation_manager = User.objects.create_user(
            username='installation_manager',
            password='test-password',
            role=Role.INSTALLATION_MANAGER,
            initials='IM',
        )

        self.technician = User.objects.create_user(
            username='technician',
            password='test-password',
            role=Role.TECHNICIAN,
            initials='TC',
        )

        self.customer = Customer.objects.create(
            legal_name='Technical Assignment Customer',
            billing_address='123 Technical Road',
            created_by=self.comptroller,
        )

        self.project = Project.objects.create(
            code='TECH-ASSIGN-001',
            customer=self.customer,
            location='Technical Assignment Location',
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state='APPROVED',
        )

    def test_installation_manager_can_assign_technician(self):

        assignment = create_technical_assignment(
            self.installation_manager,
            self.project,
            self.technician,
            date(2026, 10, 10),
        )

        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )

        self.assertEqual(
            assignment.technical_associate,
            self.technician,
        )

        self.assertEqual(
            assignment.project,
            self.project,
        )

    def test_active_assignment_can_be_ended(self):

        assignment = create_technical_assignment(
            self.installation_manager,
            self.project,
            self.technician,
            date(2026, 10, 10),
        )

        ended = end_technical_assignment(
            self.installation_manager,
            assignment.id,
        )

        self.assertEqual(
            ended.status,
            ProjectTechnicalAssignment.Status.ENDED,
        )

        self.assertIsNotNone(
            ended.ended_at,
        )

    def test_ended_assignment_cannot_be_reopened(self):

        assignment = create_technical_assignment(
            self.installation_manager,
            self.project,
            self.technician,
            date(2026, 10, 10),
        )

        end_technical_assignment(
            self.installation_manager,
            assignment.id,
        )

        assignment.status = ProjectTechnicalAssignment.Status.ACTIVE

        with self.assertRaises(Exception):
            assignment.save()