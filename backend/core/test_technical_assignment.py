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
    def test_technician_cannot_end_technical_assignment(self):
        """An unauthorized technician cannot terminate a project assignment."""
        from rest_framework.exceptions import PermissionDenied

        assignment = create_technical_assignment(
            self.installation_manager,
            self.project,
            self.technician,
            date(2026, 10, 10),
        )

        with self.assertRaises(PermissionDenied):
            end_technical_assignment(
                self.technician,
                assignment.id,
            )

        assignment.refresh_from_db()
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )
        self.assertIsNone(assignment.ended_at)

    def test_inactive_installation_manager_cannot_create_assignment(self):
        """Inactive installation managers cannot assign technicians."""
        from rest_framework.exceptions import PermissionDenied

        self.installation_manager.is_active = False
        self.installation_manager.save(update_fields=['is_active'])

        with self.assertRaises(PermissionDenied):
            create_technical_assignment(
                self.installation_manager,
                self.project,
                self.technician,
                date(2026, 10, 10),
            )

        self.assertFalse(
            ProjectTechnicalAssignment.objects.filter(
                project=self.project,
                technical_associate=self.technician,
            ).exists()
        )

    def test_inactive_technician_cannot_receive_assignment(self):
        """Inactive technicians cannot receive new project assignments."""
        from rest_framework.exceptions import ValidationError

        self.technician.is_active = False
        self.technician.save(update_fields=['is_active'])

        with self.assertRaises(ValidationError):
            create_technical_assignment(
                self.installation_manager,
                self.project,
                self.technician,
                date(2026, 10, 10),
            )

        self.assertFalse(
            ProjectTechnicalAssignment.objects.filter(
                project=self.project,
                technical_associate=self.technician,
            ).exists()
        )

    def test_ceo_temporary_installation_manager_assignment_is_audited(self):
        """Approved temporary authority permits an audited assignment without role changes."""
        from datetime import timedelta
        from django.utils import timezone
        from .models import AuditEvent, TemporaryDutyActivity, TemporaryDutyAuthorization
        from .temporary_duty_services import request_temporary_duty, approve_temporary_duty

        ceo = User.objects.create_user(
            username="technical_temporary_ceo",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
            initials="CE",
        )

        now = timezone.now()
        authorization = request_temporary_duty(
            employee=ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=ceo,
            reason="Temporary installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )
        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )
        self.assertEqual(
            approved.status,
            TemporaryDutyAuthorization.Status.APPROVED,
        )

        assignment = create_technical_assignment(
            ceo,
            self.project,
            self.technician,
            date(2026, 10, 10),
        )

        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )
        ceo.refresh_from_db()
        self.assertEqual(ceo.role, Role.CEO)

        activity = TemporaryDutyActivity.objects.get(
            authorization=approved,
            employee=ceo,
        )
        event = activity.audit_event
        self.assertEqual(event.actor_id, ceo.pk)
        self.assertEqual(event.action, "TECHNICAL_ASSIGNMENT_CREATED")
        self.assertEqual(
            event.entity_id,
            assignment.pk,
        )
    def test_unapproved_temporary_installation_manager_cannot_assign_technician(self):
        """A pending temporary-duty request grants no assignment authority."""
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.exceptions import PermissionDenied
        from .models import TemporaryDutyAuthorization
        from .temporary_duty_services import request_temporary_duty

        ceo = User.objects.create_user(
            username="technical_pending_ceo",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
            initials="CP",
        )

        now = timezone.now()
        authorization = request_temporary_duty(
            employee=ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=ceo,
            reason="Pending installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )

        self.assertEqual(
            authorization.status,
            TemporaryDutyAuthorization.Status.REQUESTED,
        )

        with self.assertRaises(PermissionDenied):
            create_technical_assignment(
                ceo,
                self.project,
                self.technician,
                date(2026, 10, 10),
            )

        self.assertFalse(
            ProjectTechnicalAssignment.objects.filter(
                project=self.project,
                assigned_by=ceo,
            ).exists()
        )

    def test_revoked_temporary_installation_manager_cannot_assign_technician(self):
        """Revoked temporary Installation Manager authority grants no permissions."""
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.exceptions import PermissionDenied
        from .models import TemporaryDutyAuthorization
        from .temporary_duty_services import (
            request_temporary_duty,
            approve_temporary_duty,
            revoke_temporary_duty,
        )

        ceo = User.objects.create_user(
            username="technical_revoked_ceo",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
            initials="CR",
        )

        now = timezone.now()
        authorization = request_temporary_duty(
            employee=ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=ceo,
            reason="Temporary installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )

        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )
        self.assertEqual(
            approved.status,
            TemporaryDutyAuthorization.Status.APPROVED,
        )

        revoked = revoke_temporary_duty(
            authorization_id=authorization.pk,
            revoked_by=self.comptroller,
            reason="Temporary coverage no longer required.",
        )
        self.assertEqual(
            revoked.status,
            TemporaryDutyAuthorization.Status.REVOKED,
        )

        with self.assertRaises(PermissionDenied):
            create_technical_assignment(
                ceo,
                self.project,
                self.technician,
                date(2026, 10, 10),
            )

        self.assertFalse(
            ProjectTechnicalAssignment.objects.filter(
                project=self.project,
                assigned_by=ceo,
            ).exists()
        )

    def test_expired_temporary_installation_manager_cannot_assign_technician(self):
        """Approved temporary authority cannot be used after its end time."""
        from datetime import timedelta
        from unittest.mock import patch
        from django.utils import timezone
        from rest_framework.exceptions import PermissionDenied
        from .models import TemporaryDutyAuthorization
        from .temporary_duty_services import (
            request_temporary_duty,
            approve_temporary_duty,
        )

        ceo = User.objects.create_user(
            username="technical_expired_ceo",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
            initials="CX",
        )

        now = timezone.now()
        authorization = request_temporary_duty(
            employee=ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=ceo,
            reason="Time-limited installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(hours=1),
        )

        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )
        self.assertEqual(
            approved.status,
            TemporaryDutyAuthorization.Status.APPROVED,
        )

        simulated_time = now + timedelta(hours=2)
        with patch(
            "django.utils.timezone.now",
            return_value=simulated_time,
        ):
            with self.assertRaises(PermissionDenied):
                create_technical_assignment(
                    ceo,
                    self.project,
                    self.technician,
                    date(2026, 10, 10),
                )

        self.assertFalse(
            ProjectTechnicalAssignment.objects.filter(
                project=self.project,
                assigned_by=ceo,
            ).exists()
        )

    def test_ceo_temporary_installation_manager_can_end_assignment_with_audit(self):
        """Temporary Installation Manager authority permits an audited assignment ending."""
        from datetime import timedelta
        from django.utils import timezone
        from .models import TemporaryDutyActivity
        from .temporary_duty_services import (
            request_temporary_duty,
            approve_temporary_duty,
        )

        ceo = User.objects.create_user(
            username="technical_end_temporary_ceo",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
            initials="CT",
        )

        assignment = create_technical_assignment(
            self.installation_manager,
            self.project,
            self.technician,
            date(2026, 10, 10),
        )

        now = timezone.now()
        authorization = request_temporary_duty(
            employee=ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=ceo,
            reason="Temporary installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )

        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        ended = end_technical_assignment(
            ceo,
            assignment.pk,
        )

        self.assertEqual(
            ended.status,
            ProjectTechnicalAssignment.Status.ENDED,
        )
        self.assertIsNotNone(ended.ended_at)

        ceo.refresh_from_db()
        self.assertEqual(ceo.role, Role.CEO)

        activity = TemporaryDutyActivity.objects.get(
            authorization=approved,
            employee=ceo,
        )
        event = activity.audit_event

        self.assertEqual(event.actor_id, ceo.pk)
        self.assertEqual(event.action, "TECHNICAL_ASSIGNMENT_ENDED")
        self.assertEqual(event.entity_id, assignment.pk)

    def test_unapproved_temporary_installation_manager_cannot_end_assignment(self):
        """Requested but unapproved temporary authority cannot end assignments."""
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.exceptions import PermissionDenied
        from .temporary_duty_services import request_temporary_duty
        from .models import TemporaryDutyActivity

        ceo = User.objects.create_user(
            username="technical_unapproved_end_ceo",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
            initials="UE",
        )

        assignment = create_technical_assignment(
            self.installation_manager,
            self.project,
            self.technician,
            date(2026, 10, 10),
        )

        now = timezone.now()
        authorization = request_temporary_duty(
            employee=ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=ceo,
            reason="Requested installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )

        with self.assertRaises(PermissionDenied):
            end_technical_assignment(ceo, assignment.pk)

        assignment.refresh_from_db()
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )
        self.assertIsNone(assignment.ended_at)
        self.assertFalse(
            TemporaryDutyActivity.objects.filter(
                authorization=authorization,
                employee=ceo,
            ).exists()
        )

    def test_revoked_temporary_installation_manager_cannot_end_assignment(self):
        """Revoked temporary Installation Manager authority cannot end assignments."""
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.exceptions import PermissionDenied
        from .models import TemporaryDutyActivity
        from .temporary_duty_services import (
            request_temporary_duty,
            approve_temporary_duty,
            revoke_temporary_duty,
        )

        ceo = User.objects.create_user(
            username="technical_revoked_end_ceo",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
            initials="RE",
        )

        assignment = create_technical_assignment(
            self.installation_manager,
            self.project,
            self.technician,
            date(2026, 10, 10),
        )

        now = timezone.now()
        authorization = request_temporary_duty(
            employee=ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=ceo,
            reason="Temporary installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )

        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        revoke_temporary_duty(
            authorization_id=approved.pk,
            revoked_by=self.comptroller,
            reason="Temporary coverage no longer required.",
        )

        with self.assertRaises(PermissionDenied):
            end_technical_assignment(ceo, assignment.pk)

        assignment.refresh_from_db()
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )
        self.assertIsNone(assignment.ended_at)
        self.assertFalse(
            TemporaryDutyActivity.objects.filter(
                authorization=authorization,
                employee=ceo,
            ).exists()
        )

    def test_expired_temporary_installation_manager_cannot_end_assignment(self):
        """Expired temporary authority cannot end technical assignments."""
        from datetime import timedelta
        from unittest.mock import patch
        from django.utils import timezone
        from rest_framework.exceptions import PermissionDenied
        from .models import TemporaryDutyActivity
        from .temporary_duty_services import (
            request_temporary_duty,
            approve_temporary_duty,
        )

        ceo = User.objects.create_user(
            username="technical_expired_end_ceo",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
            initials="EX",
        )

        assignment = create_technical_assignment(
            self.installation_manager,
            self.project,
            self.technician,
            date(2026, 10, 10),
        )

        now = timezone.now()
        authorization = request_temporary_duty(
            employee=ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=ceo,
            reason="Time-limited installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(hours=1),
        )

        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        simulated_time = now + timedelta(hours=2)
        with patch("django.utils.timezone.now", return_value=simulated_time):
            with self.assertRaises(PermissionDenied):
                end_technical_assignment(ceo, assignment.pk)

        assignment.refresh_from_db()
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )
        self.assertIsNone(assignment.ended_at)
        self.assertFalse(
            TemporaryDutyActivity.objects.filter(
                authorization=approved,
                employee=ceo,
            ).exists()
        )
