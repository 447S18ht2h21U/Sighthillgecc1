"""Development-only safety checks; no database or live routes."""
import unittest
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

from core.installation_stage_one_scheduling_adapter import (
    assess_stage_one_scheduling_candidate,
)


def preview(ready=True, blockers=(), msr_id="approved-msr-test",
            installation_authorized=False):
    return SimpleNamespace(
        msr_id=msr_id,
        requirements_satisfied=ready,
        blockers=blockers,
        installation_authorized=installation_authorized,
    )


class StageOneSchedulingAdapterTests(unittest.TestCase):
    def test_complete_stage_one_is_candidate_not_authority(self):
        result = assess_stage_one_scheduling_candidate(preview())
        self.assertTrue(result.candidate_ready)
        self.assertFalse(result.scheduling_authorized)
        self.assertFalse(result.installation_authorized)

    def test_missing_contract_blocks(self):
        result = assess_stage_one_scheduling_candidate(
            preview(False, ("Verified Contract is required.",))
        )
        self.assertFalse(result.candidate_ready)
        self.assertIn("Verified Contract is required.", result.blockers)

    def test_open_waiting_period_blocks(self):
        result = assess_stage_one_scheduling_candidate(
            preview(False, ("Waiting period remains open.",))
        )
        self.assertFalse(result.candidate_ready)

    def test_missing_payment_blocks(self):
        result = assess_stage_one_scheduling_candidate(
            preview(False, ("Bank-verified deposit is missing.",))
        )
        self.assertFalse(result.candidate_ready)

    def test_missing_preview_fails_closed(self):
        result = assess_stage_one_scheduling_candidate(None)
        self.assertFalse(result.candidate_ready)

    def test_forged_authorization_flag_fails_closed(self):
        result = assess_stage_one_scheduling_candidate(
            preview(installation_authorized=True)
        )
        self.assertFalse(result.candidate_ready)
        self.assertFalse(result.scheduling_authorized)

    def test_result_is_immutable(self):
        result = assess_stage_one_scheduling_candidate(preview())
        with self.assertRaises(FrozenInstanceError):
            result.scheduling_authorized = True


if __name__ == "__main__":
    unittest.main()
