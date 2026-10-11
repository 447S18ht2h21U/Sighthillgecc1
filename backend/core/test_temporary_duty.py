"""Security and lifecycle regression tests for temporary-duty authorization."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import AuditEvent, Role, TemporaryDutyAuthorization, User
from .temporary_duty_services import (
    approve_temporary_duty,
    close_expired_temporary_duties,
    complete_temporary_duty,
    is_temporary_duty_active,
    reject_temporary_duty,
    request_temporary_duty,
    revoke_temporary_duty,
)


class TemporaryDutyTests(TestCase):
    """Exercise temporary-duty controls using Django's isolated test database."""

    def setUp(self):
        self.ceo = User.objects.create_user(
            username="temporary_ceo", password="TestOnlyPassword2026!",
            role=Role.CEO,
        )
        self.comptroller = User.objects.create_user(
            username="temporary_comptroller", password="TestOnlyPassword2026!",
            role=Role.COMPTROLLER,
        )
        self.manager = User.objects.create_user(
            username="temporary_manager", password="TestOnlyPassword2026!",
            role=Role.SALES_MANAGER,
        )
        self.now = timezone.now()

    def request_coverage(self):
        return request_temporary_duty(
            employee=self.ceo,
            temporary_role=Role.SALES_MANAGER,
            requested_by=self.ceo,
            reason="Temporary management coverage during absence.",
            starts_at=self.now + timedelta(minutes=5),
            ends_at=self.now + timedelta(days=2),
        )

    def test_request_creates_pending_authorization_and_audit(self):
        authorization = self.request_coverage()

        self.assertEqual(
            TemporaryDutyAuthorization.objects.count(), 1
        )
        self.assertEqual(
            authorization.status,
            TemporaryDutyAuthorization.Status.REQUESTED,
        )
        self.assertEqual(authorization.permanent_role, Role.CEO)
        self.assertEqual(authorization.temporary_role, Role.SALES_MANAGER)
        self.assertEqual(authorization.employee_id, self.ceo.pk)
        self.assertIsNone(authorization.approved_by_id)
        self.assertFalse(
            is_temporary_duty_active(authorization, self.ceo)
        )

        self.ceo.refresh_from_db()
        self.assertEqual(self.ceo.role, Role.CEO)

        event = AuditEvent.objects.get(
            action="TEMPORARY_DUTY_REQUESTED",
            entity_id=authorization.pk,
        )
        self.assertEqual(event.actor_id, self.ceo.pk)
        self.assertEqual(
            event.payload["temporary_role"], Role.SALES_MANAGER
        )

    def test_independent_approval_and_audit(self):
        authorization = self.request_coverage()

        with self.assertRaises(PermissionDenied):
            approve_temporary_duty(
                authorization_id=authorization.pk,
                approver=self.ceo,
            )

        authorization.refresh_from_db()
        self.assertEqual(
            authorization.status,
            TemporaryDutyAuthorization.Status.REQUESTED,
        )

        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        self.assertEqual(
            approved.status,
            TemporaryDutyAuthorization.Status.APPROVED,
        )
        self.assertEqual(approved.approved_by_id, self.comptroller.pk)
        self.assertIsNotNone(approved.decided_at)

        self.ceo.refresh_from_db()
        self.assertEqual(self.ceo.role, Role.CEO)

        with self.assertRaises(ValidationError):
            approve_temporary_duty(
                authorization_id=authorization.pk,
                approver=self.comptroller,
            )

        event = AuditEvent.objects.get(
            action="TEMPORARY_DUTY_APPROVED",
            entity_id=authorization.pk,
        )
        self.assertEqual(event.actor_id, self.comptroller.pk)
        self.assertEqual(
            event.payload["temporary_role"], Role.SALES_MANAGER
        )

    def test_rejection_prevents_later_approval(self):
        authorization = self.request_coverage()

        with self.assertRaises(PermissionDenied):
            reject_temporary_duty(
                authorization_id=authorization.pk,
                decision_maker=self.ceo,
                reason="Self-rejection must not bypass independent oversight.",
            )

        authorization.refresh_from_db()
        self.assertEqual(
            authorization.status,
            TemporaryDutyAuthorization.Status.REQUESTED,
        )

        rejected = reject_temporary_duty(
            authorization_id=authorization.pk,
            decision_maker=self.comptroller,
            reason="Temporary coverage is not required.",
        )

        self.assertEqual(
            rejected.status,
            TemporaryDutyAuthorization.Status.REJECTED,
        )
        self.assertIsNotNone(rejected.decided_at)
        self.assertFalse(is_temporary_duty_active(rejected, self.ceo))

        with self.assertRaises(ValidationError):
            approve_temporary_duty(
                authorization_id=authorization.pk,
                approver=self.comptroller,
            )

        event = AuditEvent.objects.get(
            action="TEMPORARY_DUTY_REJECTED",
            entity_id=authorization.pk,
        )
        self.assertEqual(event.actor_id, self.comptroller.pk)

    def test_revocation_ends_approved_authority(self):
        authorization = self.request_coverage()
        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        self.assertEqual(
            approved.status,
            TemporaryDutyAuthorization.Status.APPROVED,
        )

        with self.assertRaises(PermissionDenied):
            revoke_temporary_duty(
                authorization_id=authorization.pk,
                revoked_by=self.ceo,
                reason="Self-revocation must not bypass independent oversight.",
            )

        approved.refresh_from_db()
        self.assertEqual(
            approved.status,
            TemporaryDutyAuthorization.Status.APPROVED,
        )

        revoked = revoke_temporary_duty(
            authorization_id=authorization.pk,
            revoked_by=self.comptroller,
            reason="Temporary management coverage is no longer required.",
        )

        self.assertEqual(
            revoked.status,
            TemporaryDutyAuthorization.Status.REVOKED,
        )
        self.assertIsNotNone(revoked.revoked_at)
        self.assertFalse(is_temporary_duty_active(revoked, self.ceo))

        self.ceo.refresh_from_db()
        self.assertEqual(self.ceo.role, Role.CEO)

        event = AuditEvent.objects.get(
            action="TEMPORARY_DUTY_REVOKED",
            entity_id=authorization.pk,
        )
        self.assertEqual(event.actor_id, self.comptroller.pk)

    def test_completion_ends_approved_authority(self):
        authorization = self.request_coverage()
        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        with self.assertRaises(PermissionDenied):
            complete_temporary_duty(
                authorization_id=authorization.pk,
                closed_by=self.ceo,
                reason="Self-completion is not permitted.",
            )

        approved.refresh_from_db()
        self.assertEqual(
            approved.status,
            TemporaryDutyAuthorization.Status.APPROVED,
        )

        completed = complete_temporary_duty(
            authorization_id=authorization.pk,
            closed_by=self.comptroller,
            reason="Temporary management coverage has concluded.",
        )

        self.assertEqual(
            completed.status,
            TemporaryDutyAuthorization.Status.COMPLETED,
        )
        self.assertIsNotNone(completed.closed_at)
        self.assertFalse(is_temporary_duty_active(completed, self.ceo))

        self.ceo.refresh_from_db()
        self.assertEqual(self.ceo.role, Role.CEO)

        with self.assertRaises(ValidationError):
            complete_temporary_duty(
                authorization_id=authorization.pk,
                closed_by=self.comptroller,
                reason="Duplicate completion is prohibited.",
            )

        event = AuditEvent.objects.get(
            action="TEMPORARY_DUTY_COMPLETED",
            entity_id=authorization.pk,
        )
        self.assertEqual(event.actor_id, self.comptroller.pk)

    def test_expiration_ends_authority_and_creates_audit(self):
        authorization = self.request_coverage()
        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        self.assertTrue(
            is_temporary_duty_active(
                approved,
                self.ceo,
                now=approved.starts_at,
            )
        )
        self.assertFalse(
            is_temporary_duty_active(
                approved,
                self.ceo,
                now=approved.ends_at,
            )
        )

        simulated_now = approved.ends_at + timedelta(minutes=1)

        with patch(
            "django.utils.timezone.now",
            return_value=simulated_now,
        ):
            self.assertEqual(
                close_expired_temporary_duties(
                    processed_by=self.comptroller,
                ),
                1,
            )

        approved.refresh_from_db()
        self.assertEqual(
            approved.status,
            TemporaryDutyAuthorization.Status.COMPLETED,
        )
        self.assertIsNotNone(approved.closed_at)
        self.assertFalse(is_temporary_duty_active(approved, self.ceo))

        self.assertEqual(
            close_expired_temporary_duties(
                processed_by=self.comptroller,
            ),
            0,
        )

        event = AuditEvent.objects.get(
            action="TEMPORARY_DUTY_EXPIRED",
            entity_id=authorization.pk,
        )
        self.assertEqual(event.actor_id, self.comptroller.pk)




    def test_database_rejects_authorization_date_changes(self):
        from django.db import DatabaseError, transaction

        authorization = self.request_coverage()

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                TemporaryDutyAuthorization.objects.filter(
                    pk=authorization.pk,
                ).update(
                    ends_at=authorization.ends_at + timedelta(days=1),
                )

        authorization.refresh_from_db()
        self.assertEqual(
            authorization.ends_at,
            self.now + timedelta(days=2),
        )

    def test_database_rejects_invalid_status_transition(self):
        from django.db import DatabaseError, transaction

        authorization = self.request_coverage()

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                TemporaryDutyAuthorization.objects.filter(
                    pk=authorization.pk,
                ).update(
                    status=TemporaryDutyAuthorization.Status.COMPLETED,
                )

        authorization.refresh_from_db()
        self.assertEqual(
            authorization.status,
            TemporaryDutyAuthorization.Status.REQUESTED,
        )

    def test_database_rejects_authorization_deletion(self):
        from django.db import DatabaseError, transaction

        authorization = self.request_coverage()

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                TemporaryDutyAuthorization.objects.filter(
                    pk=authorization.pk,
                ).delete()

        self.assertTrue(
            TemporaryDutyAuthorization.objects.filter(
                pk=authorization.pk,
            ).exists()
        )

    def test_database_rejects_approval_evidence_changes(self):
        from django.db import DatabaseError, transaction

        authorization = self.request_coverage()
        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                TemporaryDutyAuthorization.objects.filter(
                    pk=approved.pk,
                ).update(
                    approved_by=self.manager,
                )

        approved.refresh_from_db()
        self.assertEqual(
            approved.approved_by_id,
            self.comptroller.pk,
        )
        self.assertEqual(
            approved.status,
            TemporaryDutyAuthorization.Status.APPROVED,
        )

    def test_database_rejects_direct_approved_insert(self):
        from django.db import DatabaseError, transaction

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                TemporaryDutyAuthorization.objects.create(
                    employee=self.ceo,
                    permanent_role=self.ceo.role,
                    temporary_role=Role.SALES_MANAGER,
                    requested_by=self.ceo,
                    approved_by=self.comptroller,
                    reason="Unauthorized direct approval test",
                    starts_at=self.now + timedelta(minutes=5),
                    ends_at=self.now + timedelta(days=2),
                    status=TemporaryDutyAuthorization.Status.APPROVED,
                    decided_at=self.now,
                )

    def test_database_rejects_unauthorized_approver(self):
        """Direct database updates cannot bypass independent approval rules."""
        from django.db import DatabaseError, transaction

        authorization = self.request_coverage()

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                TemporaryDutyAuthorization.objects.filter(
                    pk=authorization.pk
                ).update(
                    status=TemporaryDutyAuthorization.Status.APPROVED,
                    approved_by=self.manager,
                    decided_at=timezone.now(),
                )

        authorization.refresh_from_db()
        self.assertEqual(
            authorization.status,
            TemporaryDutyAuthorization.Status.REQUESTED,
        )
        self.assertIsNone(authorization.approved_by_id)
        self.assertIsNone(authorization.decided_at)

    def test_database_rejects_inactive_approver(self):
        """An inactive officer cannot approve temporary authority directly."""
        from django.db import DatabaseError, transaction

        authorization = self.request_coverage()

        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                TemporaryDutyAuthorization.objects.filter(
                    pk=authorization.pk
                ).update(
                    status=TemporaryDutyAuthorization.Status.APPROVED,
                    approved_by=self.comptroller,
                    decided_at=timezone.now(),
                )

        authorization.refresh_from_db()
        self.assertEqual(
            authorization.status,
            TemporaryDutyAuthorization.Status.REQUESTED,
        )
        self.assertIsNone(authorization.approved_by_id)
        self.assertIsNone(authorization.decided_at)

    def test_database_rejects_rejection_without_timestamp(self):
        """A rejected authorization must retain decision evidence."""
        from django.db import DatabaseError, transaction

        authorization = self.request_coverage()

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                TemporaryDutyAuthorization.objects.filter(
                    pk=authorization.pk
                ).update(
                    status=TemporaryDutyAuthorization.Status.REJECTED,
                )

        authorization.refresh_from_db()
        self.assertEqual(
            authorization.status,
            TemporaryDutyAuthorization.Status.REQUESTED,
        )
        self.assertIsNone(authorization.decided_at)

    def test_database_rejects_revocation_without_timestamp(self):
        """Revoking authority requires durable revocation evidence."""
        from django.db import DatabaseError, transaction

        authorization = self.request_coverage()
        approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                TemporaryDutyAuthorization.objects.filter(
                    pk=authorization.pk
                ).update(
                    status=TemporaryDutyAuthorization.Status.REVOKED,
                )

        authorization.refresh_from_db()
        self.assertEqual(
            authorization.status,
            TemporaryDutyAuthorization.Status.APPROVED,
        )
        self.assertIsNone(authorization.revoked_at)

    def test_database_rejects_completion_timestamp_changes(self):
        """Completion evidence cannot be altered after closure."""
        from datetime import timedelta
        from django.db import DatabaseError, transaction
        from django.utils import timezone

        authorization = self.request_coverage()
        approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )
        complete_temporary_duty(
            authorization_id=authorization.pk,
            closed_by=self.comptroller,
            reason="Coverage concluded",
        )

        authorization.refresh_from_db()
        original_closed_at = authorization.closed_at
        self.assertIsNotNone(original_closed_at)

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                TemporaryDutyAuthorization.objects.filter(
                    pk=authorization.pk
                ).update(
                    closed_at=timezone.now() + timedelta(days=1),
                )

        authorization.refresh_from_db()
        self.assertEqual(
            authorization.status,
            TemporaryDutyAuthorization.Status.COMPLETED,
        )
        self.assertEqual(authorization.closed_at, original_closed_at)

    def test_inactive_approver_suspends_temporary_authority(self):
        """Temporary authority requires an active approving officer."""
        authorization = self.request_coverage()
        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        active_time = approved.starts_at + timedelta(minutes=1)

        self.assertTrue(
            is_temporary_duty_active(
                approved, self.ceo, now=active_time
            )
        )

        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])

        self.assertFalse(
            is_temporary_duty_active(
                approved, self.ceo, now=active_time
            )
        )

        self.comptroller.is_active = True
        self.comptroller.save(update_fields=["is_active"])

        self.assertTrue(
            is_temporary_duty_active(
                approved, self.ceo, now=active_time
            )
        )

        self.assertFalse(
            is_temporary_duty_active(
                approved, self.ceo, now=approved.ends_at
            )
        )

    def test_inactive_approver_detected_with_stale_user_object(self):
        """Authorization must reflect current database account status."""
        from .models import User

        authorization = self.request_coverage()
        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        active_time = approved.starts_at + timedelta(minutes=1)

        self.assertTrue(
            is_temporary_duty_active(
                approved, self.ceo, now=active_time
            )
        )

        User.objects.filter(pk=self.comptroller.pk).update(
            is_active=False
        )

        self.assertFalse(
            is_temporary_duty_active(
                approved, self.ceo, now=active_time
            )
        )

    def test_revoked_authorization_detected_with_stale_object(self):
        """Revoked temporary authority must not survive in a cached object."""
        authorization = self.request_coverage()
        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        active_time = approved.starts_at + timedelta(minutes=1)

        self.assertTrue(
            is_temporary_duty_active(
                approved, self.ceo, now=active_time
            )
        )

        TemporaryDutyAuthorization.objects.filter(
            pk=approved.pk
        ).update(
            status=TemporaryDutyAuthorization.Status.REVOKED,
            revoked_at=timezone.now(),
        )

        self.assertFalse(
            is_temporary_duty_active(
                approved, self.ceo, now=active_time
            )
        )
