
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from .models import Role
from .expedited_envelope_preview_4568 import build_unified_envelope_preview
from .expedited_offline_envelope_4568 import assemble_offline_candidate

VALIDATOR = "core.expedited_tab_contract_4568.validate_offline_tab_contract"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class MandatoryAssemblyGate4568Tests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            pk=uuid4(), role=Role.SALES_MANAGER, is_active=True
        )
        self.identity = {
            "project_id": str(uuid4()),
            "msr_id": str(uuid4()),
            "msr_version": 3,
            "snapshot_sha256": "a" * 64,
            "proposed_date": "2026-11-15",
            "envelope_count": 1,
            "documents": ["CUSTOMER_SOW", "EXPEDITED_SERVICE"],
            "recipients": [
                {
                    "role": role,
                    "recipient_id": str(n),
                    "routing_order": n,
                    "name": "Fictional " + role,
                    "email": "fictional%d@example.invalid" % n,
                }
                for n, role in enumerate(
                    ("CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER"),
                    1,
                )
            ],
            "expedited_signer_authorized": False,
            "send_authorized": False,
            "installation_authorized": False,
        }

    def preview(self):
        module = "core.expedited_envelope_preview_4568"
        with (
            patch(f"{module}.User.objects.filter") as users,
            patch(f"{module}.assess_unified_recipients",
                  return_value=self.identity),
        ):
            users.return_value.first.return_value = self.actor
            return build_unified_envelope_preview(
                actor=self.actor, project_id=self.identity["project_id"]
            )

    def test_assembly_calls_real_validator(self):
        with patch(VALIDATOR, wraps=__import__(
            "core.expedited_tab_contract_4568",
            fromlist=["validate_offline_tab_contract"]
        ).validate_offline_tab_contract) as validator:
            candidate = assemble_offline_candidate(preview=self.preview())
            validator.assert_called_once()
            self.assertEqual(
                candidate["status"], "UNSENDABLE_OFFLINE_CANDIDATE"
            )
            self.assertFalse(candidate["send_authorized"])

    def test_validator_rejection_blocks_assembly(self):
        with patch(VALIDATOR, side_effect=ValidationError(
            "Invalid reviewer decision"
        )):
            with self.assertRaises(ValidationError):
                assemble_offline_candidate(preview=self.preview())

    def test_validator_sending_claim_blocks_assembly(self):
        response = {
            "status": "OFFLINE_TAB_CONTRACT_VALIDATED",
            "provider_behavior_verified": False,
            "send_authorized": True,
            "installation_authorized": False,
        }
        with patch(VALIDATOR, return_value=response):
            with self.assertRaises(ValidationError):
                assemble_offline_candidate(preview=self.preview())

    def test_validator_unknown_response_blocks_assembly(self):
        with patch(VALIDATOR, return_value=None):
            with self.assertRaises(ValidationError):
                assemble_offline_candidate(preview=self.preview())
