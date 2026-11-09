"""Database-backed test-only technician payroll provenance regression."""
from datetime import date
from unittest.mock import patch

from django.test import TestCase

from .models import (
    AuditEvent,
    AuditHead,
    Customer,
    Outbox,
    Project,
    ProjectTechnicalAssignment,
    Role,
    User,
)
from .technical_assignment_services import (
    create_technical_assignment,
    end_technical_assignment,
)
from .payroll_technical_provenance_4296 import (
    candidate_database_technical_role,
    database_technical_provenance_grants_live_access,
)


EARNED = date(2026, 10, 12)


class DatabaseTechnicalProvenance4296Tests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="provenance_4296_manager",
            role=Role.INSTALLATION_MANAGER,
        )
        self.comptroller = User.objects.create_user(
            username="provenance_4296_comptroller",
            role=Role.COMPTROLLER,
        )
        self.technician = User.objects.create_user(
            username="provenance_4296_technician",
            role=Role.TECHNICIAN,
        )
        self.other = User.objects.create_user(
            username="provenance_4296_other",
            role=Role.TECHNICIAN,
        )
        customer = Customer.objects.create(
            legal_name="Provenance Test Customer",
            billing_address="Test-only address",
            created_by=self.comptroller,
        )
        self.project = Project.objects.create(
            code="PROVENANCE-4296-A",
            customer=customer,
            location="Test-only location",
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state="APPROVED",
        )
        self.other_project = Project.objects.create(
            code="PROVENANCE-4296-B",
            customer=customer,
            location="Second test-only location",
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state="APPROVED",
        )

    def assign(self, subject=None, project=None):
        return create_technical_assignment(
            actor=self.manager,
            project=self.project if project is None else project,
            technical_associate=self.technician if subject is None else subject,
            effective_date=date(2026, 10, 10),
        )

    def classify(self, subject=None, project=None, earned=EARNED):
        return candidate_database_technical_role(
            subject_id=(self.technician if subject is None else subject).pk,
            project_id=(self.project if project is None else project).pk,
            earned_on=earned,
        )

    def test_real_service_assignment_has_matching_audit(self):
        assignment = self.assign()
        events = AuditEvent.objects.filter(
            entity_id=assignment.pk,
            action="TECHNICAL_ASSIGNMENT_CREATED",
        )
        self.assertEqual(events.count(), 1)
        self.assertEqual(self.classify(), Role.TECHNICIAN)
        self.assertFalse(database_technical_provenance_grants_live_access())

    def test_other_person_is_not_classified(self):
        self.assign()
        self.assertIsNone(self.classify(subject=self.other))

    def test_other_project_is_not_classified(self):
        self.assign()
        self.assertIsNone(self.classify(project=self.other_project))

    def test_direct_record_without_audit_is_rejected(self):
        ProjectTechnicalAssignment.objects.create(
            project=self.project,
            technical_associate=self.technician,
            assigned_by=self.manager,
            effective_date=date(2026, 10, 10),
            status=ProjectTechnicalAssignment.Status.ACTIVE,
        )
        self.assertIsNone(self.classify())

    def test_ended_then_reassigned_overlap_is_ambiguous(self):
        first = self.assign()
        end_technical_assignment(self.manager, first.pk)
        self.assign()
        self.assertIsNone(self.classify())

    def test_invalid_subject_project_or_earning_date_denied(self):
        self.assign()
        self.assertIsNone(candidate_database_technical_role(
            subject_id="not-a-uuid",
            project_id=self.project.pk,
            earned_on=EARNED,
        ))
        self.assertIsNone(candidate_database_technical_role(
            subject_id=self.technician.pk,
            project_id="not-a-uuid",
            earned_on=EARNED,
        ))
        self.assertIsNone(self.classify(earned=None))

    def test_provenance_read_does_not_change_audit_or_assignments(self):
        assignment = self.assign()
        before = (
            tuple(AuditHead.objects.values_list(
                "sequence", "digest"
            ).get(pk=1)),
            AuditEvent.objects.count(),
            Outbox.objects.count(),
            ProjectTechnicalAssignment.objects.count(),
        )

        self.assertEqual(self.classify(), Role.TECHNICIAN)

        after = (
            tuple(AuditHead.objects.values_list(
                "sequence", "digest"
            ).get(pk=1)),
            AuditEvent.objects.count(),
            Outbox.objects.count(),
            ProjectTechnicalAssignment.objects.count(),
        )

        self.assertEqual(before, after)
        self.assertTrue(ProjectTechnicalAssignment.objects.filter(
            pk=assignment.pk
        ).exists())