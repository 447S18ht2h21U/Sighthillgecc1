"""Permanent forged-service-plan regression for the isolated test bridge."""

from uuid import uuid4

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .msr_delegation_service_plan import DelegationServicePlan
from .test_msr_delegation_transaction_bridge import (
    invoke_only_in_disposable_test,
)


class ForgedServicePlanTests(TestCase):
    def test_unexpected_extra_argument_denied(self):
        plan = DelegationServicePlan(
            "approve_fixed_msr_delegation",
            (
                ("request_id", uuid4()),
                ("approver_id", uuid4()),
                ("reason", "Independent documented approval"),
                ("override", True),
            ),
        )
        with self.assertRaises(PermissionDenied):
            invoke_only_in_disposable_test(plan)

    def test_invalid_actor_identifier_denied(self):
        plan = DelegationServicePlan(
            "approve_fixed_msr_delegation",
            (
                ("request_id", uuid4()),
                ("approver_id", "forged-actor"),
                ("reason", "Independent documented approval"),
            ),
        )
        with self.assertRaises(PermissionDenied):
            invoke_only_in_disposable_test(plan)

    def test_invalid_termination_kind_denied(self):
        plan = DelegationServicePlan(
            "terminate_fixed_msr_delegation",
            (
                ("decision_id", uuid4()),
                ("actor_id", uuid4()),
                ("kind", "FORGED_KIND"),
                ("reason", "Documented invalid termination"),
            ),
        )
        with self.assertRaises(PermissionDenied):
            invoke_only_in_disposable_test(plan)