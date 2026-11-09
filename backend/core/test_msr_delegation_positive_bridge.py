"""Positive transaction tests through the isolated delegation bridge.

Inherits the existing reassignment fixture and its eight regression tests.
All writes occur inside Django's disposable test database.
No operational URLs or production dispatchers are connected.
"""

from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from .models import AuditEvent
from .msr_delegation_api_boundary import PreparedDelegationCommand
from .msr_delegation_service_plan import prepare_service_plan
from .test_msr_delegation_transaction_bridge import (
    invoke_only_in_disposable_test,
    MSRDelegationRequest,
    MSRDelegationDecision,
    MSRDelegationTermination,
    MSRDelegationProjectInvalidation,
)
from .test_msr_delegation_reassignment_service import (
    ReassignmentInvalidationTests,
)


class PositiveDelegationBridgeTests(ReassignmentInvalidationTests):
    """Reuse verified roles, project ownership, audit head, and decision."""

    def bridge(self, action, actor, values, target=None):
        command = PreparedDelegationCommand(
            action=action,
            actor_id=actor.pk,
            arguments=tuple(sorted(values.items())),
        )
        plan = prepare_service_plan(command, route_target=target)
        return invoke_only_in_disposable_test(plan)

    def request_values(self):
        now = timezone.now()
        return {
            "recipient_id": self.recipient.pk,
            "source_associate_id": self.source.pk,
            "project_ids": (self.project_b.pk,),
            "starts_at": now - timedelta(minutes=1),
            "ends_at": now + timedelta(hours=1),
            "reason": "Documented temporary sales project coverage",
        }

    def test_bridge_positive_request_and_independent_approval(self):
        old_requests = MSRDelegationRequest.objects.count()
        old_decisions = MSRDelegationDecision.objects.count()
        old_requested_audits = AuditEvent.objects.filter(
            action="msr.delegation.requested"
        ).count()
        old_approved_audits = AuditEvent.objects.filter(
            action="msr.delegation.approved"
        ).count()

        request = self.bridge(
            "request", self.manager, self.request_values()
        )
        self.assertEqual(MSRDelegationRequest.objects.count(), old_requests + 1)
        self.assertEqual(request.manager_id, self.manager.pk)
        self.assertEqual(request.recipient_id, self.recipient.pk)
        self.assertTrue(request.read_only)

        decision = self.bridge(
            "approve",
            self.comptroller,
            {"reason": "Independent approval of temporary coverage"},
            target=request.pk,
        )
        self.assertEqual(decision.request_id, request.pk)
        self.assertEqual(decision.decided_by_id, self.comptroller.pk)
        self.assertEqual(decision.result, "APPROVED")
        self.assertEqual(MSRDelegationDecision.objects.count(), old_decisions + 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                action="msr.delegation.requested"
            ).count(),
            old_requested_audits + 1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                action="msr.delegation.approved"
            ).count(),
            old_approved_audits + 1,
        )

    def test_bridge_positive_recipient_surrender(self):
        previous = MSRDelegationTermination.objects.count()
        event = self.bridge(
            "surrender",
            self.recipient,
            {
                "kind": "VOLUNTARY_SURRENDER",
                "reason": "Recipient voluntarily surrendered coverage",
            },
            target=self.decision.pk,
        )
        self.assertEqual(event.kind, "VOLUNTARY_SURRENDER")
        self.assertEqual(event.terminated_by_id, self.recipient.pk)
        self.assertEqual(
            MSRDelegationTermination.objects.count(), previous + 1
        )

    def test_bridge_positive_executive_revocation(self):
        previous = MSRDelegationTermination.objects.count()
        event = self.bridge(
            "revoke",
            self.comptroller,
            {
                "kind": "ADMINISTRATIVE_REVOCATION",
                "reason": "Independent documented executive revocation",
            },
            target=self.decision.pk,
        )
        self.assertEqual(event.kind, "ADMINISTRATIVE_REVOCATION")
        self.assertEqual(event.terminated_by_id, self.comptroller.pk)
        self.assertEqual(
            MSRDelegationTermination.objects.count(), previous + 1
        )

    def test_bridge_positive_reassignment_invalidates_scope(self):
        previous = MSRDelegationProjectInvalidation.objects.count()
        result = self.bridge(
            "reassign",
            self.comptroller,
            {
                "new_owner_id": self.recipient.pk,
                "reason": "Documented reassignment to a new sales owner",
            },
            target=self.project_a.pk,
        )
        self.assertEqual(result.sales_associate_id, self.recipient.pk)
        self.assertEqual(result.ownership_revision, 1)
        self.assertEqual(
            MSRDelegationProjectInvalidation.objects.count(),
            previous + 1,
        )
        self.project_b.refresh_from_db()
        self.assertEqual(self.project_b.ownership_revision, 0)

    def test_bridge_audit_failure_rolls_back_new_request(self):
        old_requests = MSRDelegationRequest.objects.count()
        old_audits = AuditEvent.objects.count()

        with patch(
            "core.msr_delegation_request_service.audit",
            side_effect=RuntimeError("synthetic audit failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "synthetic audit failure"
            ):
                self.bridge(
                    "request", self.manager, self.request_values()
                )

        self.assertEqual(MSRDelegationRequest.objects.count(), old_requests)
        self.assertEqual(AuditEvent.objects.count(), old_audits)

    def test_bridge_full_request_approval_surrender_lifecycle(self):
        request = self.bridge(
            "request", self.manager, self.request_values()
        )
        decision = self.bridge(
            "approve",
            self.comptroller,
            {"reason": "Independent documented lifecycle approval"},
            target=request.pk,
        )
        termination = self.bridge(
            "surrender",
            self.recipient,
            {
                "kind": "VOLUNTARY_SURRENDER",
                "reason": "Recipient completes documented temporary coverage",
            },
            target=decision.pk,
        )

        self.assertEqual(decision.request_id, request.pk)
        self.assertEqual(termination.decision_id, decision.pk)
        self.assertEqual(termination.terminated_by_id, self.recipient.pk)
        self.assertEqual(termination.kind, "VOLUNTARY_SURRENDER")

        for action in (
            "msr.delegation.requested",
            "msr.delegation.approved",
            "msr.delegation.terminated",
        ):
            self.assertGreaterEqual(
                AuditEvent.objects.filter(action=action).count(), 1
            )

    def test_bridge_reassignment_invalidates_only_selected_project(self):
        before = MSRDelegationProjectInvalidation.objects.count()
        self.bridge(
            "reassign",
            self.comptroller,
            {
                "new_owner_id": self.recipient.pk,
                "reason": "Documented single-project owner reassignment",
            },
            target=self.project_a.pk,
        )

        self.assertEqual(
            MSRDelegationProjectInvalidation.objects.count(), before + 1
        )
        invalidated = list(
            MSRDelegationProjectInvalidation.objects.values_list(
                "scope__project_id", flat=True
            )
        )
        self.assertIn(self.project_a.pk, invalidated)
        self.assertNotIn(self.project_b.pk, invalidated)

        self.project_b.refresh_from_db()
        self.assertEqual(self.project_b.sales_associate_id, self.source.pk)
        self.assertEqual(self.project_b.ownership_revision, 0)

    def test_bridge_approval_audit_failure_rolls_back_decision(self):
        request = self.bridge(
            "request", self.manager, self.request_values()
        )
        old_decisions = MSRDelegationDecision.objects.count()
        old_audits = AuditEvent.objects.count()

        with patch(
            "core.msr_delegation_approval_service.audit",
            side_effect=RuntimeError("synthetic approval audit failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "synthetic approval audit failure"
            ):
                self.bridge(
                    "approve",
                    self.comptroller,
                    {"reason": "Independent approval with rollback evidence"},
                    target=request.pk,
                )

        self.assertEqual(
            MSRDelegationDecision.objects.count(), old_decisions
        )
        self.assertEqual(AuditEvent.objects.count(), old_audits)
        self.assertFalse(
            MSRDelegationDecision.objects.filter(
                request_id=request.pk
            ).exists()
        )