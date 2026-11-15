from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from django.db import DatabaseError
from django.test import SimpleTestCase
from django.utils import timezone

from core.installation_start_control_4565 import (
    assess_installation_start,
)


class InstallationStartEquipment5043Tests(SimpleTestCase):

    def assess(self, *, required=2, reviewed=1, complete=False,
               failure=None):
        project = SimpleNamespace(
            pk=UUID("12345678-1234-1234-1234-123456789abc")
        )
        schedule = SimpleNamespace(
            schedule_verified=True,
            blockers=(),
        )
        contract = SimpleNamespace(
            customer_contract_signature_recorded=True,
            generated_contract_integrity_verified=True,
        )
        equipment = SimpleNamespace(
            total_units=required,
            reviewed_candidate_units=reviewed,
            all_units_reviewed=complete,
            blockers=(
                "Unit review is incomplete.",
            ) if not complete else (),
        )

        with (
            patch(
                "core.installation_start_control_4565."
                "assess_database_schedule",
                return_value=schedule,
            ),
            patch(
                "core.installation_start_control_4565."
                "ensure_installation_eligible",
                return_value=True,
            ),
            patch(
                "core.installation_start_control_4565."
                "assess_contract_evidence",
                return_value=contract,
            ),
            patch(
                "core.installation_start_control_4565."
                "assess_expedited_chain",
                return_value={"expedited_chain_reviewed": False},
            ),
            patch(
                "core.installation_start_control_4565."
                "preview_installation_with_physical_reviews",
                side_effect=failure,
                return_value=equipment,
            ) as preview,
        ):
            result = assess_installation_start(
                project=project,
                proposed_start=timezone.now(),
            )

        preview.assert_called_once()
        return result

    def test_incomplete_reviews_are_reported_and_blocked(self):
        result = self.assess()

        self.assertEqual(result["physical_units_required"], 2)
        self.assertEqual(result["physical_units_reviewed"], 1)
        self.assertFalse(result["all_physical_units_reviewed"])
        self.assertTrue(any(
            "independent accepted review" in reason
            for reason in result["blockers"]
        ))
        self.assertFalse(result["installation_authorized"])
        self.assertFalse(result["installation_started"])
        self.assertFalse(result["trusted_equipment_verified"])

    def test_fully_reviewed_candidates_do_not_grant_authority(self):
        result = self.assess(required=2, reviewed=2, complete=True)

        self.assertTrue(result["all_physical_units_reviewed"])
        self.assertTrue(result["commercial_ready"])
        self.assertTrue(result["schedule_verified"])
        self.assertFalse(result["trusted_equipment_verified"])
        self.assertFalse(result["installation_authorized"])
        self.assertFalse(result["installation_started"])

    def test_unavailable_evidence_fails_closed(self):
        result = self.assess(failure=DatabaseError("schema unavailable"))

        self.assertEqual(result["physical_units_required"], 0)
        self.assertEqual(result["physical_units_reviewed"], 0)
        self.assertFalse(result["all_physical_units_reviewed"])
        self.assertFalse(result["installation_authorized"])
        self.assertTrue(any(
            "could not be independently verified" in reason
            for reason in result["blockers"]
        ))
