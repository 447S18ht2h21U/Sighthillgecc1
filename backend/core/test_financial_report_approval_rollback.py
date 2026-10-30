"""Financial report approval audit rollback regression."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from .financial_report_services import approve_financial_report
from .models import AuditEvent, AuditHead, FinancialReport, Outbox, Role, User


class FinancialReportApprovalRollbackTests(TestCase):

    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="financial_approval_rollback_comptroller",
            password="isolated-test-only",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.report = FinancialReport.objects.create(
            kind=FinancialReport.Kind.INCOME_STATEMENT,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            report_snapshot={"revenue": "100.00"},
            created_by=self.comptroller,
        )

    def test_audit_failure_rolls_back_financial_approval(self):
        original_events = AuditEvent.objects.count()
        original_outbox = Outbox.objects.count()

        head = AuditHead.objects.get(pk=1)
        original_sequence = head.sequence
        original_digest = head.digest

        with patch(
            "core.financial_report_services.audit",
            side_effect=RuntimeError("Simulated financial approval audit failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Simulated financial approval audit failure"
            ):
                approve_financial_report(
                    self.comptroller,
                    self.report.pk,
                )

        self.report.refresh_from_db()
        head.refresh_from_db()

        self.assertEqual(self.report.status, FinancialReport.Status.DRAFT)
        self.assertIsNone(self.report.approved_by_id)
        self.assertIsNone(self.report.approved_at)

        self.assertEqual(AuditEvent.objects.count(), original_events)
        self.assertEqual(Outbox.objects.count(), original_outbox)
        self.assertEqual(head.sequence, original_sequence)
        self.assertEqual(head.digest, original_digest)

    def test_duplicate_approval_is_rejected(self):
        from rest_framework.exceptions import ValidationError

        first = approve_financial_report(
            self.comptroller, self.report.pk
        )

        original_approver = first.approved_by_id
        original_approved_at = first.approved_at
        original_events = AuditEvent.objects.count()
        original_outbox = Outbox.objects.count()

        head = AuditHead.objects.get(pk=1)
        original_sequence = head.sequence
        original_digest = head.digest

        with self.assertRaises(ValidationError):
            approve_financial_report(
                self.comptroller, self.report.pk
            )

        self.report.refresh_from_db()
        head.refresh_from_db()

        self.assertEqual(
            self.report.status, FinancialReport.Status.APPROVED
        )
        self.assertEqual(
            self.report.approved_by_id, original_approver
        )
        self.assertEqual(
            self.report.approved_at, original_approved_at
        )
        self.assertEqual(AuditEvent.objects.count(), original_events)
        self.assertEqual(Outbox.objects.count(), original_outbox)
        self.assertEqual(head.sequence, original_sequence)
        self.assertEqual(head.digest, original_digest)

    def test_missing_report_approval_is_rejected(self):
        from uuid import uuid4

        from .models import FinancialReport

        missing_id = uuid4()
        original_events = AuditEvent.objects.count()
        original_outbox = Outbox.objects.count()
        original_reports = FinancialReport.objects.count()

        head = AuditHead.objects.get(pk=1)
        original_sequence = head.sequence
        original_digest = head.digest

        with self.assertRaises(FinancialReport.DoesNotExist):
            approve_financial_report(
                self.comptroller, missing_id
            )

        self.report.refresh_from_db()
        head.refresh_from_db()

        self.assertEqual(
            self.report.status, FinancialReport.Status.DRAFT
        )
        self.assertIsNone(self.report.approved_by_id)
        self.assertIsNone(self.report.approved_at)
        self.assertEqual(
            FinancialReport.objects.count(), original_reports
        )
        self.assertEqual(AuditEvent.objects.count(), original_events)
        self.assertEqual(Outbox.objects.count(), original_outbox)
        self.assertEqual(head.sequence, original_sequence)
        self.assertEqual(head.digest, original_digest)

    def test_successful_approval_creates_integrity_evidence(self):
        original_events = AuditEvent.objects.count()
        original_outbox = Outbox.objects.count()

        head = AuditHead.objects.get(pk=1)
        original_sequence = head.sequence
        original_digest = head.digest

        approved = approve_financial_report(
            self.comptroller, self.report.pk
        )

        self.assertEqual(
            approved.status, FinancialReport.Status.APPROVED
        )
        self.assertEqual(
            approved.approved_by_id, self.comptroller.pk
        )
        self.assertIsNotNone(approved.approved_at)

        self.assertEqual(
            AuditEvent.objects.count(), original_events + 1
        )
        self.assertEqual(
            Outbox.objects.count(), original_outbox + 1
        )

        event = AuditEvent.objects.get(
            action="financial_report.approved",
            entity_id=self.report.pk,
        )

        self.assertEqual(event.actor_id, self.comptroller.pk)
        self.assertEqual(event.sequence, original_sequence + 1)
        self.assertEqual(event.previous_hash, original_digest)

        head.refresh_from_db()
        self.assertEqual(head.sequence, event.sequence)
        self.assertEqual(head.digest, event.digest)

        outbox = Outbox.objects.get(event=event)
        self.assertEqual(outbox.topic, "financial_report.approved")
        self.assertEqual(
            outbox.payload["audit_id"], str(event.pk)
        )
        self.assertEqual(
            outbox.payload["entity_id"], str(self.report.pk)
        )