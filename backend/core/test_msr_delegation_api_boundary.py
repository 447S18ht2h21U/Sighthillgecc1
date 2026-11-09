"""Non-database command-boundary regressions."""

import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from rest_framework.exceptions import PermissionDenied

from core.msr_delegation_api_boundary import (
    prepare_delegation_command,
    execute_prepared_delegation_command,
    boundary_grants_live_msr_access,
)
from core.msr_delegation_api_contract import DelegationInputError


class DelegationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.actor = uuid4()
        self.payload = {
            "recipient_id": str(uuid4()),
            "source_associate_id": str(uuid4()),
            "project_ids": [str(uuid4())],
            "starts_at": "2026-11-01T10:00:00-04:00",
            "ends_at": "2026-11-02T10:00:00-05:00",
            "reason": "Documented temporary coverage",
        }
        self.request = SimpleNamespace(
            method="POST",
            data=self.payload,
        )

    def prepare(self, action):
        with patch(
            "core.msr_delegation_api_boundary.verified_delegation_actor",
            return_value=SimpleNamespace(pk=self.actor),
        ) as verification:
            command = prepare_delegation_command(
                self.request, action=action
            )
            verification.assert_called_once_with(
                self.request, action=action
            )
            return command

    def test_request_command_uses_verified_actor(self):
        command = self.prepare("request")
        self.assertEqual(command.actor_id, self.actor)
        self.assertEqual(command.action, "request")
        self.assertNotIn("manager_id", dict(command.arguments))

    def test_approval_command(self):
        self.request.data = {"reason": "Independent approval"}
        self.assertEqual(self.prepare("approve").action, "approve")

    def test_surrender_command(self):
        self.request.data = {
            "kind": "VOLUNTARY_SURRENDER",
            "reason": "Coverage is no longer needed",
        }
        self.assertEqual(self.prepare("surrender").action, "surrender")

    def test_revocation_command(self):
        self.request.data = {
            "kind": "ADMINISTRATIVE_REVOCATION",
            "reason": "Administrative access revocation",
        }
        self.assertEqual(self.prepare("revoke").action, "revoke")

    def test_reassignment_command(self):
        self.request.data = {
            "new_owner_id": str(uuid4()),
            "reason": "Approved project ownership change",
        }
        self.assertEqual(self.prepare("reassign").action, "reassign")

    def test_surrender_cannot_revoke(self):
        self.request.data = {
            "kind": "ADMINISTRATIVE_REVOCATION",
            "reason": "Documented administrative action",
        }
        with self.assertRaises(PermissionDenied):
            self.prepare("surrender")

    def test_revoke_cannot_surrender(self):
        self.request.data = {
            "kind": "VOLUNTARY_SURRENDER",
            "reason": "Documented voluntary surrender",
        }
        with self.assertRaises(PermissionDenied):
            self.prepare("revoke")

    def test_get_rejected_before_actor_lookup(self):
        self.request.method = "GET"
        with patch(
            "core.msr_delegation_api_boundary.verified_delegation_actor"
        ) as verification:
            with self.assertRaises(PermissionDenied):
                prepare_delegation_command(
                    self.request, action="request"
                )
            verification.assert_not_called()

    def test_unknown_action_rejected(self):
        with self.assertRaises(PermissionDenied):
            prepare_delegation_command(
                self.request, action="admin"
            )

    def test_client_supplied_actor_rejected(self):
        self.request.data["manager_id"] = str(uuid4())
        with self.assertRaises(DelegationInputError):
            self.prepare("request")

    def test_missing_body_rejected(self):
        self.request.data = None
        with self.assertRaises(DelegationInputError):
            self.prepare("request")

    def test_command_is_frozen(self):
        command = self.prepare("request")
        with self.assertRaises(FrozenInstanceError):
            command.actor_id = uuid4()

    def test_command_arguments_are_immutable_tuple(self):
        command = self.prepare("request")
        self.assertIs(type(command.arguments), tuple)
        self.assertIs(type(dict(command.arguments)["project_ids"]), tuple)

    def test_service_dispatch_always_denied(self):
        with self.assertRaises(PermissionDenied):
            execute_prepared_delegation_command(
                self.prepare("request")
            )

    def test_boundary_never_grants_access(self):
        self.assertIs(boundary_grants_live_msr_access(), False)

    def test_no_route_registration(self):
        root = Path(__file__).resolve().parents[1]
        urls = (root / "config" / "urls.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertNotIn("msr_delegation_api_boundary", urls)
        self.assertNotIn("msr-delegations", urls)


if __name__ == "__main__":
    unittest.main()