from django.db import DatabaseError, connection, transaction
from django.test import TestCase

from . import test_temporary_project_access as temporary_access_fixtures
from .models import TemporaryProjectAccessAuthorization


class ProjectAccessInsertGuardTest(TestCase):

    def setUp(self):
        temporary_access_fixtures.TemporaryProjectAccessTests.setUp(self)

    def _pending_project_access(self):
        return (
            temporary_access_fixtures.TemporaryProjectAccessTests
            ._pending_project_access(self)
        )
    def test_direct_approved_insert_is_rejected(self):
        access = self._pending_project_access()
        table = "core_temporaryprojectaccessauthorization"
        trigger_name = "gecc_temporary_project_access_insert_guard"

        with connection.cursor() as cursor:
            if connection.vendor == "sqlite":
                cursor.execute(
                    "SELECT sql FROM sqlite_master WHERE type = %s AND name = %s",
                    ["trigger", trigger_name],
                )
                trigger = cursor.fetchone()
            elif connection.vendor == "postgresql":
                cursor.execute(
                    """
                    SELECT 1 FROM pg_trigger
                    WHERE tgrelid = %s::regclass
                      AND tgname = %s
                      AND NOT tgisinternal
                      AND tgenabled = 'O'
                    """,
                    [table, trigger_name],
                )
                trigger = cursor.fetchone()
            else:
                self.fail("Unsupported database for project-access trigger test.")

            self.assertIsNotNone(trigger)

            columns = [
                field.name
                for field in connection.introspection.get_table_description(
                    cursor, table
                )
                if field.name != "id"
            ]

            column_sql = ", ".join(
                connection.ops.quote_name(column) for column in columns
            )

            cursor.execute(
                f"SELECT {column_sql} FROM {connection.ops.quote_name(table)} "
                "WHERE id = %s",
                [access.pk.hex if connection.vendor == "sqlite" else access.pk],
            )
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        values = list(row)
        values[columns.index("status")] = "APPROVED"

        placeholders = ", ".join(["%s"] * len(columns))

        with self.assertRaisesRegex(
            DatabaseError,
            "Temporary project access must begin as an unapproved request",
        ):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"INSERT INTO {connection.ops.quote_name(table)} "
                        f"({column_sql}) VALUES ({placeholders})",
                        values,
                    )


class ProjectAccessUpdateGuardTest(TestCase):

    def setUp(self):
        temporary_access_fixtures.TemporaryProjectAccessTests.setUp(self)

    def _pending_project_access(self):
        return (
            temporary_access_fixtures.TemporaryProjectAccessTests
            ._pending_project_access(self)
        )
    def test_project_assignment_is_immutable(self):
        access = self._pending_project_access()

        with self.assertRaisesRegex(
            DatabaseError,
            "Project-access request details are immutable",
        ):
            with transaction.atomic():
                TemporaryProjectAccessAuthorization.objects.filter(
                    pk=access.pk
                ).update(project=self.other_project)

    def test_direct_approval_without_evidence_is_rejected(self):
        access = self._pending_project_access()

        with self.assertRaisesRegex(
            DatabaseError,
            "Independent project-access approval required|Project-access approver or temporary duty is not authorized",
        ):
            with transaction.atomic():
                TemporaryProjectAccessAuthorization.objects.filter(
                    pk=access.pk
                ).update(status="APPROVED")

    def test_invalid_status_transition_is_rejected(self):
        access = self._pending_project_access()

        with self.assertRaisesRegex(
            DatabaseError,
            "Invalid project-access status transition",
        ):
            with transaction.atomic():
                TemporaryProjectAccessAuthorization.objects.filter(
                    pk=access.pk
                ).update(status="COMPLETED")

    def test_authorization_deletion_is_rejected(self):
        access = self._pending_project_access()

        with self.assertRaisesRegex(
            DatabaseError,
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
            DatabaseError,
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
            DatabaseError,
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
