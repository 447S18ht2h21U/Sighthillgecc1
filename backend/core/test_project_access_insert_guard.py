from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from .test_temporary_project_access import TemporaryProjectAccessTests
from .models import TemporaryProjectAccessAuthorization


class ProjectAccessInsertGuardTest(TemporaryProjectAccessTests):
    def test_direct_approved_insert_is_rejected(self):
        access = self._pending_project_access()
        table = "core_temporaryprojectaccessauthorization"

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type = %s AND name = %s",
                ["trigger", "gecc_temporary_project_access_insert_guard"],
            )
            trigger = cursor.fetchone()

        self.assertIsNotNone(trigger)

        with connection.cursor() as cursor:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [
                row[1] for row in cursor.fetchall()
                if row[1] != "id"
            ]

        with connection.cursor() as cursor:
            column_sql = ", ".join(f'"{column}"' for column in columns)
            cursor.execute(
                f"SELECT {column_sql} FROM {table} WHERE id = %s",
                [access.pk.hex],
            )
            values = list(cursor.fetchone())

        values[columns.index("status")] = "APPROVED"

        column_sql = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join(["%s"] * len(columns))

        with self.assertRaisesRegex(
            IntegrityError,
            "Temporary project access must begin as an unapproved request",
        ):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})",
                        values,
                    )


class ProjectAccessUpdateGuardTest(TemporaryProjectAccessTests):
    def test_project_assignment_is_immutable(self):
        access = self._pending_project_access()

        with self.assertRaisesRegex(
            IntegrityError,
            "Project-access request details are immutable",
        ):
            with transaction.atomic():
                TemporaryProjectAccessAuthorization.objects.filter(
                    pk=access.pk
                ).update(project=self.other_project)

    def test_direct_approval_without_evidence_is_rejected(self):
        access = self._pending_project_access()

        with self.assertRaisesRegex(
            IntegrityError,
            "Independent project-access approval required|Project-access approver or temporary duty is not authorized",
        ):
            with transaction.atomic():
                TemporaryProjectAccessAuthorization.objects.filter(
                    pk=access.pk
                ).update(status="APPROVED")

    def test_invalid_status_transition_is_rejected(self):
        access = self._pending_project_access()

        with self.assertRaisesRegex(
            IntegrityError,
            "Invalid project-access status transition",
        ):
            with transaction.atomic():
                TemporaryProjectAccessAuthorization.objects.filter(
                    pk=access.pk
                ).update(status="COMPLETED")

    def test_authorization_deletion_is_rejected(self):
        access = self._pending_project_access()

        with self.assertRaisesRegex(
            IntegrityError,
            "Project-access authorizations cannot be deleted",
        ):
            with transaction.atomic():
                TemporaryProjectAccessAuthorization.objects.filter(
                    pk=access.pk
                ).delete()

    def test_database_rejects_unauthorized_approver(self):
        from django.utils import timezone

        access = self._pending_project_access()

        with self.assertRaisesRegex(
            IntegrityError,
            "Project-access approver or temporary duty is not authorized",
        ):
            with transaction.atomic():
                TemporaryProjectAccessAuthorization.objects.filter(
                    pk=access.pk
                ).update(
                    status="APPROVED",
                    approved_by=self.manager,
                    decided_at=timezone.now(),
                )

    def test_database_rejects_revoked_underlying_duty(self):
        from django.utils import timezone
        from .models import TemporaryDutyAuthorization

        access = self._pending_project_access()

        TemporaryDutyAuthorization.objects.filter(
            pk=access.temporary_duty_id
        ).update(
            status="REVOKED",
            revoked_at=timezone.now(),
        )

        with self.assertRaisesRegex(
            IntegrityError,
            "Project-access approver or temporary duty is not authorized",
        ):
            with transaction.atomic():
                TemporaryProjectAccessAuthorization.objects.filter(
                    pk=access.pk
                ).update(
                    status="APPROVED",
                    approved_by=self.comptroller,
                    decided_at=timezone.now(),
                )
