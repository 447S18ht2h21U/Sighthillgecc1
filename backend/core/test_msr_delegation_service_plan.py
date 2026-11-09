"""Service mapping tests without database access or operational dispatch."""

import unittest
from uuid import uuid4
from rest_framework.exceptions import PermissionDenied

from core.msr_delegation_api_boundary import PreparedDelegationCommand
from core.msr_delegation_service_plan import (
    CONTRACTS, prepare_service_plan, execute_service_plan,
)


class DelegationServicePlanTests(unittest.TestCase):
    def setUp(self):
        self.actor = uuid4()
        self.target = uuid4()

    def command(self, action, values):
        return PreparedDelegationCommand(
            action=action,
            actor_id=self.actor,
            arguments=tuple(sorted(values.items())),
        )

    def test_request_binds_manager_from_actor(self):
        values = {
            "recipient_id": uuid4(), "source_associate_id": uuid4(),
            "project_ids": (uuid4(),),
            "starts_at": "validated-start",
            "ends_at": "validated-end",
            "reason": "Documented delegation reason",
        }
        plan = prepare_service_plan(self.command("request", values))
        self.assertEqual(plan.operation, CONTRACTS["request"][0])
        self.assertEqual(dict(plan.arguments)["manager_id"], self.actor)

    def test_approval_binds_trusted_target(self):
        plan = prepare_service_plan(
            self.command("approve", {"reason": "Independent approval"}),
            route_target=self.target,
        )
        self.assertEqual(dict(plan.arguments)["approver_id"], self.actor)
        self.assertEqual(dict(plan.arguments)["request_id"], self.target)

    def test_surrender_mapping(self):
        values = {
            "kind": "VOLUNTARY_SURRENDER",
            "reason": "Documented voluntary surrender",
        }
        plan = prepare_service_plan(
            self.command("surrender", values), route_target=self.target
        )
        self.assertEqual(dict(plan.arguments)["decision_id"], self.target)

    def test_revocation_mapping(self):
        values = {
            "kind": "ADMINISTRATIVE_REVOCATION",
            "reason": "Documented executive revocation",
        }
        plan = prepare_service_plan(
            self.command("revoke", values), route_target=self.target
        )
        self.assertEqual(dict(plan.arguments)["actor_id"], self.actor)

    def test_reassignment_mapping(self):
        plan = prepare_service_plan(
            self.command("reassign", {
                "new_owner_id": uuid4(),
                "reason": "Documented ownership change",
            }),
            route_target=self.target,
        )
        self.assertEqual(dict(plan.arguments)["project_id"], self.target)

    def test_missing_route_target_denied(self):
        with self.assertRaises(PermissionDenied):
            prepare_service_plan(
                self.command("approve", {"reason": "Independent approval"})
            )

    def test_request_with_target_denied(self):
        with self.assertRaises(PermissionDenied):
            prepare_service_plan(
                self.command("request", {}),
                route_target=self.target,
            )

    def test_client_actor_override_denied(self):
        with self.assertRaises(PermissionDenied):
            prepare_service_plan(
                self.command("approve", {
                    "reason": "Independent approval",
                    "approver_id": uuid4(),
                }),
                route_target=self.target,
            )

    def test_wrong_termination_kind_denied(self):
        with self.assertRaises(PermissionDenied):
            prepare_service_plan(
                self.command("surrender", {
                    "kind": "ADMINISTRATIVE_REVOCATION",
                    "reason": "Documented attempted revocation",
                }),
                route_target=self.target,
            )

    def test_duplicate_argument_denied(self):
        command = PreparedDelegationCommand(
            action="approve",
            actor_id=self.actor,
            arguments=(
                ("reason", "First documented reason"),
                ("reason", "Second documented reason"),
            ),
        )
        with self.assertRaises(PermissionDenied):
            prepare_service_plan(command, route_target=self.target)

    def test_invalid_actor_denied(self):
        command = PreparedDelegationCommand(
            "approve", None, (("reason", "Documented approval"),)
        )
        with self.assertRaises(PermissionDenied):
            prepare_service_plan(command, route_target=self.target)

    def test_all_service_execution_denied(self):
        with self.assertRaises(PermissionDenied):
            execute_service_plan(None)


if __name__ == "__main__":
    unittest.main()