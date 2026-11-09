"""Isolated standard-library tests; no Django or database is required."""

import unittest
from uuid import uuid4

from core.msr_delegation_api_contract import (
    DelegationInputError,
    parse_request_payload,
    parse_approval_payload,
    parse_termination_payload,
    parse_reassignment_payload,
    api_contract_grants_live_msr_access,
)


class DelegationAPIContractTests(unittest.TestCase):
    def setUp(self):
        self.recipient = str(uuid4())
        self.source = str(uuid4())
        self.project = str(uuid4())
        self.payload = {
            "recipient_id": self.recipient,
            "source_associate_id": self.source,
            "project_ids": [self.project],
            "starts_at": "2026-11-01T10:00:00-04:00",
            "ends_at": "2026-11-02T10:00:00-05:00",
            "reason": "Temporary documented coverage",
        }

    def test_valid_fixed_request(self):
        result = parse_request_payload(self.payload)
        self.assertEqual(len(result["project_ids"]), 1)
        self.assertNotIn("manager_id", result)

    def test_caller_cannot_supply_manager_authority(self):
        self.payload["manager_id"] = str(uuid4())
        with self.assertRaises(DelegationInputError):
            parse_request_payload(self.payload)

    def test_recipient_cannot_equal_source(self):
        self.payload["recipient_id"] = self.source
        with self.assertRaises(DelegationInputError):
            parse_request_payload(self.payload)

    def test_duplicate_projects_rejected(self):
        self.payload["project_ids"] *= 2
        with self.assertRaises(DelegationInputError):
            parse_request_payload(self.payload)

    def test_empty_project_scope_rejected(self):
        self.payload["project_ids"] = []
        with self.assertRaises(DelegationInputError):
            parse_request_payload(self.payload)

    def test_oversized_project_scope_rejected(self):
        self.payload["project_ids"] = [str(uuid4()) for _ in range(101)]
        with self.assertRaises(DelegationInputError):
            parse_request_payload(self.payload)

    def test_naive_timestamp_rejected(self):
        self.payload["starts_at"] = "2026-11-01T10:00:00"
        with self.assertRaises(DelegationInputError):
            parse_request_payload(self.payload)

    def test_reverse_dates_rejected(self):
        self.payload["starts_at"] = "2026-11-03T10:00:00-05:00"
        with self.assertRaises(DelegationInputError):
            parse_request_payload(self.payload)

    def test_invalid_uuid_rejected(self):
        self.payload["recipient_id"] = "not-a-uuid"
        with self.assertRaises(DelegationInputError):
            parse_request_payload(self.payload)

    def test_short_reason_rejected(self):
        self.payload["reason"] = "short"
        with self.assertRaises(DelegationInputError):
            parse_request_payload(self.payload)

    def test_valid_approval_contract(self):
        self.assertEqual(
            parse_approval_payload({"reason": "Independent approval"})["reason"],
            "Independent approval",
        )

    def test_approval_cannot_supply_approver_identity(self):
        with self.assertRaises(DelegationInputError):
            parse_approval_payload({
                "reason": "Independent approval",
                "approver_id": str(uuid4()),
            })

    def test_valid_termination_contract(self):
        result = parse_termination_payload({
            "kind": "VOLUNTARY_SURRENDER",
            "reason": "Coverage is no longer needed",
        })
        self.assertEqual(result["kind"], "VOLUNTARY_SURRENDER")

    def test_unsupported_termination_rejected(self):
        with self.assertRaises(DelegationInputError):
            parse_termination_payload({
                "kind": "AUTOMATIC_EXPIRATION",
                "reason": "Coverage period has ended",
            })

    def test_reassignment_cannot_supply_actor(self):
        with self.assertRaises(DelegationInputError):
            parse_reassignment_payload({
                "new_owner_id": str(uuid4()),
                "actor_id": str(uuid4()),
                "reason": "Authorized project reassignment",
            })

    def test_no_live_access_activation(self):
        self.assertFalse(api_contract_grants_live_msr_access())


if __name__ == "__main__":
    unittest.main()