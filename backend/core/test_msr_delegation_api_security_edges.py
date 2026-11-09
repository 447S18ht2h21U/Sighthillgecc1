"""Adversarial API contract checks; no Django database or live endpoint."""

import unittest
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from core.msr_delegation_api_contract import (
    DelegationInputError,
    parse_request_payload,
    parse_approval_payload,
    parse_termination_payload,
    parse_reassignment_payload,
    api_contract_grants_live_msr_access,
)


class DelegationSecurityEdgeTests(unittest.TestCase):

    def setUp(self):
        self.payload = {
            "recipient_id": str(uuid4()),
            "source_associate_id": str(uuid4()),
            "project_ids": [str(uuid4())],
            "starts_at": "2026-11-01T09:00:00-04:00",
            "ends_at": "2026-11-03T09:00:00-05:00",
            "reason": "Documented temporary project coverage",
        }

    def reject(self, payload):
        with self.assertRaises(DelegationInputError):
            parse_request_payload(payload)

    def test_null_payload(self):
        self.reject(None)

    def test_array_payload(self):
        self.reject([])

    def test_missing_required_field(self):
        item = deepcopy(self.payload)
        del item["reason"]
        self.reject(item)

    def test_unexpected_privilege_flag(self):
        item = deepcopy(self.payload)
        item["read_only"] = False
        self.reject(item)

    def test_client_supplied_approval_status(self):
        item = deepcopy(self.payload)
        item["approved"] = True
        self.reject(item)

    def test_client_supplied_ownership_revision(self):
        item = deepcopy(self.payload)
        item["ownership_revision"] = 0
        self.reject(item)

    def test_boolean_identifier(self):
        item = deepcopy(self.payload)
        item["recipient_id"] = True
        self.reject(item)

    def test_null_project_identifier(self):
        item = deepcopy(self.payload)
        item["project_ids"] = [None]
        self.reject(item)

    def test_zero_uuid(self):
        item = deepcopy(self.payload)
        item["recipient_id"] = str(uuid4()).replace(
            str(uuid4()), "unused"
        ) if False else "00000000-0000-0000-0000-000000000000"
        self.reject(item)

    def test_reason_is_not_a_string(self):
        item = deepcopy(self.payload)
        item["reason"] = {"text": "Documented coverage"}
        self.reject(item)

    def test_excessively_long_reason(self):
        item = deepcopy(self.payload)
        item["reason"] = "x" * 2001
        self.reject(item)

    def test_equal_start_and_end(self):
        item = deepcopy(self.payload)
        item["ends_at"] = item["starts_at"]
        self.reject(item)

    def test_invalid_timezone_timestamp(self):
        item = deepcopy(self.payload)
        item["ends_at"] = "2026-11-03T09:00:00"
        self.reject(item)

    def test_invalid_timestamp_type(self):
        item = deepcopy(self.payload)
        item["starts_at"] = 123
        self.reject(item)

    def test_no_client_approval_decision_field(self):
        with self.assertRaises(DelegationInputError):
            parse_approval_payload({
                "reason": "Independent executive decision",
                "result": "APPROVED",
            })

    def test_no_client_termination_actor(self):
        with self.assertRaises(DelegationInputError):
            parse_termination_payload({
                "kind": "ADMINISTRATIVE_REVOCATION",
                "reason": "Documented administrative revocation",
                "actor_id": str(uuid4()),
            })

    def test_no_client_reassignment_revision(self):
        with self.assertRaises(DelegationInputError):
            parse_reassignment_payload({
                "new_owner_id": str(uuid4()),
                "reason": "Documented ownership reassignment",
                "new_revision": 100,
            })

    def test_contract_cannot_grant_access(self):
        self.assertIs(api_contract_grants_live_msr_access(), False)
        self.assertIs(
            api_contract_grants_live_msr_access(
                approved=True, role="CEO"
            ),
            False,
        )

    def test_no_database_or_service_dispatch_in_contract(self):
        path = Path(__file__).with_name(
            "msr_delegation_api_contract.py"
        )
        text = path.read_text(encoding="utf-8-sig")
        forbidden = (
            "from django",
            "import django",
            "objects.",
            "transaction.atomic",
            "create_fixed_msr_delegation_request",
            "approve_fixed_msr_delegation",
            "terminate_fixed_msr_delegation",
            "reassign_project_with_msr_invalidation",
        )
        for token in forbidden:
            self.assertNotIn(token, text)

    def test_no_operational_route_registration(self):
        root = Path(__file__).resolve().parents[1]
        urls = (root / "config" / "urls.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertNotIn("msr_delegation_api_contract", urls)
        self.assertNotIn("msr-delegations", urls)


if __name__ == "__main__":
    unittest.main()