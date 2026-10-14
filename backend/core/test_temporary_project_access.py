"""Security and lifecycle regression tests for temporary project access."""

from datetime import timedelta

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from .models import Customer, Project, Role, TemporaryProjectAccessAuthorization, User
from .temporary_project_access_services import (
    request_temporary_project_access,
    approve_temporary_project_access,
    revoke_temporary_project_access,
    validate_project_access_request,
)
from .temporary_duty_services import (
    approve_temporary_duty,
    request_temporary_duty,
)


class TemporaryProjectAccessTests(TestCase):
    """Verify separation of temporary authority and project access."""

    def setUp(self):
        self.ceo = User.objects.create_user(
            username="project_access_ceo",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
        )
        self.comptroller = User.objects.create_user(
            username="project_access_comptroller",
            password="TestOnlyPassword2026!",
            role=Role.COMPTROLLER,
        )

        self.manager = User.objects.create_user(
            username="project_access_manager",
            role=Role.SALES_MANAGER,
            initials="SM",
        )
        self.sales = User.objects.create_user(
            username="project_access_sales",
            role=Role.SALES_ASSOCIATE,
            initials="SA",
        )
        customer = Customer.objects.create(
            legal_name="Temporary Access Test Customer",
            billing_address="10 Example Street",
            created_by=self.comptroller,
        )
        self.project = Project.objects.create(
            code="TEMP-ACCESS-001",
            customer=customer,
            location="10 Example Street",
            sales_associate=self.sales,
            reviewer=self.manager,
        )
        self.other_project = Project.objects.create(
            code="TEMP-ACCESS-002",
            customer=customer,
            location="12 Example Street",
            sales_associate=self.sales,
            reviewer=self.manager,
        )

    def test_approved_temporary_duty_does_not_create_project_access(self):
        now = timezone.now()

        authorization = request_temporary_duty(
            employee=self.ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=self.ceo,
            reason="Temporary installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )

        approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        self.assertFalse(
            TemporaryProjectAccessAuthorization.objects.filter(
                employee=self.ceo,
                temporary_duty=authorization,
            ).exists()
        )


    def test_requested_project_access_is_not_approved(self):
        now = timezone.now()

        duty = request_temporary_duty(
            employee=self.ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=self.ceo,
            reason="Temporary installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )

        approve_temporary_duty(
            authorization_id=duty.pk,
            approver=self.comptroller,
        )

        access = TemporaryProjectAccessAuthorization.objects.create(
            temporary_duty=duty,
            employee=self.ceo,
            project=self.project,
            requested_by=self.ceo,
            reason="Coverage for this specific installation.",
            starts_at=now,
            ends_at=now + timedelta(days=1),
        )

        self.assertEqual(
            access.status,
            TemporaryProjectAccessAuthorization.Status.REQUESTED,
        )
        self.assertIsNone(access.approved_by_id)
        self.assertIsNone(access.decided_at)
        self.assertEqual(access.project_id, self.project.pk)
        self.assertEqual(
            TemporaryProjectAccessAuthorization.objects.filter(
                employee=self.ceo,
                status=TemporaryProjectAccessAuthorization.Status.APPROVED,
            ).count(),
            0,
        )


    def test_inactive_employee_cannot_request_project_access(self):
        now = timezone.now()

        duty = request_temporary_duty(
            employee=self.ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=self.ceo,
            reason="Temporary installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )

        approve_temporary_duty(
            authorization_id=duty.pk,
            approver=self.comptroller,
        )

        self.ceo.is_active = False
        self.ceo.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            validate_project_access_request(
                employee=self.ceo,
                temporary_duty=duty,
                starts_at=now,
                ends_at=now + timedelta(days=1),
            )


    def test_project_access_cannot_exceed_temporary_duty_period(self):
        now = timezone.now()
        duty = request_temporary_duty(
            employee=self.ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=self.ceo,
            reason="Temporary installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )
        approve_temporary_duty(
            authorization_id=duty.pk,
            approver=self.comptroller,
        )

        with self.assertRaises(ValidationError):
            validate_project_access_request(
                employee=self.ceo,
                temporary_duty=duty,
                starts_at=now,
                ends_at=now + timedelta(days=3),
            )


    def test_project_access_request_is_pending_and_audited(self):
        from .models import AuditEvent

        now = timezone.now()
        duty = request_temporary_duty(
            employee=self.ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=self.ceo,
            reason="Temporary installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )
        approve_temporary_duty(
            authorization_id=duty.pk,
            approver=self.comptroller,
        )

        access = request_temporary_project_access(
            employee=self.ceo,
            temporary_duty=duty,
            project=self.project,
            requested_by=self.ceo,
            reason="Project-specific installation coverage.",
            starts_at=now,
            ends_at=now + timedelta(days=1),
        )

        self.assertEqual(
            access.status,
            TemporaryProjectAccessAuthorization.Status.REQUESTED,
        )
        self.assertIsNone(access.approved_by_id)
        self.assertIsNone(access.decided_at)
        self.assertEqual(access.project_id, self.project.pk)
        self.assertEqual(access.employee_id, self.ceo.pk)
        self.assertEqual(access.temporary_duty_id, duty.pk)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="TEMPORARY_PROJECT_ACCESS_REQUESTED",
                entity_id=access.pk,
            ).exists()
        )


    def _pending_project_access(self):
        now = timezone.now()
        duty = request_temporary_duty(
            employee=self.ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=self.ceo,
            reason="Temporary installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )
        approve_temporary_duty(
            authorization_id=duty.pk,
            approver=self.comptroller,
        )
        return request_temporary_project_access(
            employee=self.ceo,
            temporary_duty=duty,
            project=self.project,
            requested_by=self.ceo,
            reason="Project-specific installation coverage.",
            starts_at=now,
            ends_at=now + timedelta(days=1),
        )

    def test_independent_project_access_approval(self):
        from .models import AuditEvent

        access = self._pending_project_access()
        approved = approve_temporary_project_access(
            authorization_id=access.pk,
            approver=self.comptroller,
        )

        self.assertEqual(
            approved.status,
            TemporaryProjectAccessAuthorization.Status.APPROVED,
        )
        self.assertEqual(approved.approved_by_id, self.comptroller.pk)
        self.assertIsNotNone(approved.decided_at)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="TEMPORARY_PROJECT_ACCESS_APPROVED",
                entity_id=access.pk,
            ).exists()
        )

    def test_project_access_self_approval_rejected(self):
        access = self._pending_project_access()

        with self.assertRaises(PermissionDenied):
            approve_temporary_project_access(
                authorization_id=access.pk,
                approver=self.ceo,
            )

        access.refresh_from_db()
        self.assertEqual(
            access.status,
            TemporaryProjectAccessAuthorization.Status.REQUESTED,
        )

    def test_unauthorized_project_access_approver_rejected(self):
        access = self._pending_project_access()

        with self.assertRaises(PermissionDenied):
            approve_temporary_project_access(
                authorization_id=access.pk,
                approver=self.manager,
            )

        access.refresh_from_db()
        self.assertEqual(
            access.status,
            TemporaryProjectAccessAuthorization.Status.REQUESTED,
        )


    def test_approved_access_reveals_only_authorized_project(self):
        from .operational_visibility import operational_project_scope

        access = self._pending_project_access()

        before = set(
            operational_project_scope(self.ceo).values_list("pk", flat=True)
        )
        self.assertNotIn(self.project.pk, before)
        self.assertNotIn(self.other_project.pk, before)

        approve_temporary_project_access(
            authorization_id=access.pk,
            approver=self.comptroller,
        )

        visible = set(
            operational_project_scope(self.ceo).values_list("pk", flat=True)
        )

        self.assertEqual(visible, {self.project.pk})
        self.assertNotIn(self.other_project.pk, visible)


    def test_expired_project_access_removes_visibility(self):
        from .operational_visibility import operational_project_scope

        access = self._pending_project_access()

        approve_temporary_project_access(
            authorization_id=access.pk,
            approver=self.comptroller,
        )

        self.assertTrue(
            operational_project_scope(self.ceo).filter(
                pk=self.project.pk
            ).exists()
        )

        from unittest.mock import patch

        simulated_time = access.ends_at + timedelta(seconds=1)

        with patch(
            "core.operational_visibility.timezone.now",
            return_value=simulated_time,
        ):
            self.assertFalse(
                operational_project_scope(self.ceo).filter(
                    pk=self.project.pk
                ).exists()
            )

        access.refresh_from_db()
        self.assertEqual(
            access.status,
            TemporaryProjectAccessAuthorization.Status.APPROVED,
        )
        self.assertIsNone(access.revoked_at)


    def test_revoked_project_access_removes_visibility(self):
        from .operational_visibility import operational_project_scope

        access = self._pending_project_access()

        approve_temporary_project_access(
            authorization_id=access.pk,
            approver=self.comptroller,
        )

        self.assertTrue(
            operational_project_scope(self.ceo).filter(
                pk=self.project.pk
            ).exists()
        )

        TemporaryProjectAccessAuthorization.objects.filter(
            pk=access.pk
        ).update(
            status=TemporaryProjectAccessAuthorization.Status.REVOKED,
            revoked_at=timezone.now(),
        )

        self.assertFalse(
            operational_project_scope(self.ceo).filter(
                pk=self.project.pk
            ).exists()
        )


    def test_controlled_revocation_is_audited_and_preserves_temporary_duty(self):
        from .models import AuditEvent, TemporaryDutyAuthorization
        from .operational_visibility import operational_project_scope

        access = self._pending_project_access()
        approve_temporary_project_access(
            authorization_id=access.pk,
            approver=self.comptroller,
        )

        self.assertTrue(
            operational_project_scope(self.ceo).filter(
                pk=self.project.pk
            ).exists()
        )

        revoked = revoke_temporary_project_access(
            authorization_id=access.pk,
            revoked_by=self.comptroller,
            reason="Temporary project coverage withdrawn.",
        )

        self.assertEqual(
            revoked.status,
            TemporaryProjectAccessAuthorization.Status.REVOKED,
        )
        self.assertIsNotNone(revoked.revoked_at)

        self.assertFalse(
            operational_project_scope(self.ceo).filter(
                pk=self.project.pk
            ).exists()
        )

        duty = TemporaryDutyAuthorization.objects.get(
            pk=access.temporary_duty_id
        )
        self.assertEqual(
            duty.status,
            TemporaryDutyAuthorization.Status.APPROVED,
        )

        self.assertTrue(
            AuditEvent.objects.filter(
                action="TEMPORARY_PROJECT_ACCESS_REVOKED",
                entity_id=access.pk,
            ).exists()
        )


    def test_unauthorized_project_access_revocation_rejected(self):
        access = self._pending_project_access()
        approve_temporary_project_access(
            authorization_id=access.pk,
            approver=self.comptroller,
        )

        with self.assertRaises(PermissionDenied):
            revoke_temporary_project_access(
                authorization_id=access.pk,
                revoked_by=self.manager,
                reason="Unauthorized revocation attempt.",
            )

        access.refresh_from_db()
        self.assertEqual(
            access.status,
            TemporaryProjectAccessAuthorization.Status.APPROVED,
        )
        self.assertIsNone(access.revoked_at)

    def test_duplicate_project_access_revocation_rejected(self):
        from .models import AuditEvent

        access = self._pending_project_access()
        approve_temporary_project_access(
            authorization_id=access.pk,
            approver=self.comptroller,
        )

        revoke_temporary_project_access(
            authorization_id=access.pk,
            revoked_by=self.comptroller,
            reason="Coverage withdrawn.",
        )

        with self.assertRaises(ValidationError):
            revoke_temporary_project_access(
                authorization_id=access.pk,
                revoked_by=self.comptroller,
                reason="Second revocation attempt.",
            )

        access.refresh_from_db()
        self.assertEqual(
            access.status,
            TemporaryProjectAccessAuthorization.Status.REVOKED,
        )

        self.assertEqual(
            AuditEvent.objects.filter(
                action="TEMPORARY_PROJECT_ACCESS_REVOKED",
                entity_id=access.pk,
            ).count(),
            1,
        )
