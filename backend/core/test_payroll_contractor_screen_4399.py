"""Five focused, database-free fictional contractor tests."""

from copy import deepcopy
from unittest import TestCase

from payroll_contractor_screen_4399 import (
    format_fictional_contractor_screen_4399 as format_screen,
    contractor_screen_4399_grants_live_access,
)


def engagement(**changes):
    data = {
        "reference": "TEST-ENG-01",
        "contractor_id": "TEST-CTR-001",
        "display_name": "Fictional Contractor Alpha",
        "return_of": None,
        "engagement_status": "PENDING",
        "start_date": "2026-01-05",
        "end_date": None,
        "w9": "APPROVED",
        "drivers_license": "PENDING",
        "agreement": "APPROVED",
        "payment_eligible": False,
    }
    data.update(changes)
    return data


def fixture():
    return {
        "view": "fictional_contractor_records_only",
        "backend_access_verified": False,
        "onboarding_authority_granted": False,
        "live_payroll_authorized": False,
        "payment_actions_authorized": False,
        "rows": [engagement()],
    }


class ContractorScreen4399Tests(TestCase):

    def test_01_pending_onboarding_is_not_payment_eligible(self):
        result = format_screen(fixture())
        self.assertEqual(
            result["rows"][0]["drivers_license"], "PENDING"
        )
        self.assertFalse(result["rows"][0]["payment_eligible"])

    def test_02_active_requires_all_approved_documents(self):
        data = fixture()
        data["rows"][0].update({
            "engagement_status": "ACTIVE",
            "payment_eligible": True,
        })
        with self.assertRaises(ValueError):
            format_screen(data)

        data["rows"][0]["drivers_license"] = "APPROVED"
        result = format_screen(data)
        self.assertTrue(result["rows"][0]["payment_eligible"])

    def test_03_historical_return_links_are_preserved(self):
        data = fixture()
        data["rows"] = [
            engagement(
                engagement_status="ENDED",
                end_date="2026-06-30",
            ),
            engagement(
                reference="TEST-ENG-R01",
                return_of="TEST-ENG-01",
                start_date="2026-07-06",
                drivers_license="APPROVED",
                engagement_status="ACTIVE",
                payment_eligible=True,
            ),
        ]

        result = format_screen(data)
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(
            result["rows"][1]["return_of"], "TEST-ENG-01"
        )

        data["rows"][1]["start_date"] = "2026-06-30"
        with self.assertRaises(ValueError):
            format_screen(data)

    def test_04_unsafe_state_and_authority_fail_closed(self):
        data = fixture()
        data["backend_access_verified"] = True
        with self.assertRaises(ValueError):
            format_screen(data)

        data = fixture()
        data["rows"].append(deepcopy(data["rows"][0]))
        with self.assertRaises(ValueError):
            format_screen(data)

        data = fixture()
        data["rows"][0]["return_of"] = "TEST-MISSING"
        with self.assertRaises(ValueError):
            format_screen(data)

        data = fixture()
        data["rows"][0]["start_date"] = "2026-02-30"
        with self.assertRaises(ValueError):
            format_screen(data)

    def test_05_private_fields_and_live_actions_excluded(self):
        data = fixture()
        data["rows"][0]["tax_identifier"] = "SECRET-PRIVATE"
        data["rows"][0]["license_image"] = "SECRET-PRIVATE"
        data["rows"][0]["bank_account"] = "SECRET-PRIVATE"
        data["company_total"] = "SECRET-PRIVATE"

        original = deepcopy(data)
        result = format_screen(data)

        self.assertEqual(data, original)
        self.assertNotIn("SECRET-PRIVATE", str(result))
        self.assertFalse(result["backend_access_verified"])
        self.assertFalse(result["onboarding_authority_granted"])
        self.assertFalse(result["live_payroll_authorized"])
        self.assertFalse(contractor_screen_4399_grants_live_access())
