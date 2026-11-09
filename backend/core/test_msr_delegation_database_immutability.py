"""Real-record immutability checks on disposable in-memory SQLite.

Triggers are installed inside the Django TestCase transaction, never
on a persistent database and never by an operational migration.
"""

from datetime import timedelta

from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from core.models import AuditHead, Customer, Project, Role, User
from core.msr_delegation_request_service import (
    create_fixed_msr_delegation_request,
)
from core.msr_delegation_approval_service import (
    approve_fixed_msr_delegation,
)
from core.msr_delegation_termination_service import (
    terminate_fixed_msr_delegation,
)
from core.msr_delegation_reassignment_service import (
    reassign_project_with_msr_invalidation,
)
from core.msr_delegation_sqlite_guards import (
    EVIDENCE_TABLES,
    install_isolated_evidence_guards,
)


class RealRecordImmutabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def person(name, role):
            return User.objects.create_user(
                username="msr3861" + name,
                password="isolated-test-only",
                role=role,
                initials=name[:3].upper(),
            )

        cls.manager = person("manager", Role.SALES_MANAGER)
        cls.source = person("source", Role.SALES_ASSOCIATE)
        cls.recipient = person("recipient", Role.SALES_ASSOCIATE)
        cls.next_owner = person("nextowner", Role.SALES_ASSOCIATE)
        cls.comptroller = person("comptroller", Role.COMPTROLLER)
        cls.ceo = person("ceo", Role.CEO)

        cls.customer = Customer.objects.create(
            created_by=cls.manager,
            legal_name="MSR Immutable Evidence Test Customer",
            billing_address="Test Only",
            phone="5550000105",
            email="msr-immutable@example.invalid",
        )
        cls.project = Project.objects.create(
            code="MSR-IMMUTABLE-3861",
            customer=cls.customer,
            location="Disposable Test Project",
            sales_associate=cls.source,
            reviewer=cls.manager,
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)
        now = timezone.now()

        request = create_fixed_msr_delegation_request(
            manager_id=self.manager.pk,
            recipient_id=self.recipient.pk,
            source_associate_id=self.source.pk,
            project_ids=[self.project.pk],
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(hours=1),
            reason="Temporary audited project coverage requirement",
        )

        decision = approve_fixed_msr_delegation(
            request_id=request.pk,
            approver_id=self.comptroller.pk,
            reason="Independent approval of temporary project coverage",
        )

        terminate_fixed_msr_delegation(
            decision_id=decision.pk,
            actor_id=self.ceo.pk,
            kind="ADMINISTRATIVE_REVOCATION",
            reason="Temporary project coverage administratively revoked",
        )

        reassign_project_with_msr_invalidation(
            project_id=self.project.pk,
            new_owner_id=self.next_owner.pk,
            actor_id=self.comptroller.pk,
            reason="Approved owner reassignment for evidence testing",
        )

        self.assertEqual(len(EVIDENCE_TABLES), 5)
        self.assertEqual(install_isolated_evidence_guards(connection), 10)

    def _record(self, table):
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT "id" FROM "{table}" LIMIT 1')
            row = cursor.fetchone()
        self.assertIsNotNone(row, f"Missing historical evidence: {table}")
        return row[0]

    def test_each_evidence_table_has_a_record(self):
        for table in EVIDENCE_TABLES:
            with self.subTest(table=table):
                self.assertIsNotNone(self._record(table))

    def test_ten_triggers_attached(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            )
            actual = {row[0] for row in cursor.fetchall()}

        expected = {
            f"msr_immutable_{table}_{action}"
            for table in EVIDENCE_TABLES
            for action in ("update", "delete")
        }
        self.assertTrue(expected.issubset(actual))

    def test_direct_sql_update_and_delete_blocked(self):
        checks = 0
        for table in EVIDENCE_TABLES:
            identifier = self._record(table)
            for action in ("UPDATE", "DELETE"):
                with self.subTest(table=table, action=action):
                    if action == "UPDATE":
                        statement = (
                            f'UPDATE "{table}" SET "id" = "id" '
                            'WHERE "id" = %s'
                        )
                    else:
                        statement = (
                            f'DELETE FROM "{table}" WHERE "id" = %s'
                        )

                    with self.assertRaisesRegex(
                        IntegrityError,
                        "MSR delegation evidence is immutable",
                    ):
                        with transaction.atomic():
                            with connection.cursor() as cursor:
                                cursor.execute(statement, [identifier])

                    self.assertEqual(self._record(table), identifier)
                    checks += 1

        self.assertEqual(checks, 10)

    def test_django_queryset_update_is_blocked(self):
        from core.msr_delegation_models import MSRDelegationRequest

        with self.assertRaisesRegex(
            IntegrityError,
            "MSR delegation evidence is immutable",
        ):
            with transaction.atomic():
                MSRDelegationRequest.objects.update(
                    reason="Unauthorized historical alteration"
                )

    def test_protection_does_not_grant_live_access(self):
        from core.msr_delegation_eligibility_service import (
            eligibility_check_grants_live_msr_access,
        )
        self.assertFalse(eligibility_check_grants_live_msr_access())