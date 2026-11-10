from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase

from .expedited_envelope_contract_4567 import FIELDS
from .expedited_signing_remaining_layout_4567 import (
    REMAINING, complete_visual_candidate,
)

ROOT = (
    Path(settings.BASE_DIR).parent
    / "docs/reference/GECC-20261107-final-seven"
)


class RemainingExpeditedLayout4567Tests(SimpleTestCase):
    def setUp(self):
        self.result = complete_visual_candidate(ROOT)

    def test_all_required_fields_have_candidate_rectangles(self):
        self.assertEqual(len(self.result["tabs"]), len(FIELDS))
        self.assertEqual(len(self.result["tabs"]), 17)

    def test_thirteen_additional_fields(self):
        self.assertEqual(self.result["new_candidate_count"], 13)
        self.assertEqual(len(REMAINING), 13)

    def test_sow_signatures_belong_to_page_two(self):
        for key in (
            "sow_customer_signature", "sow_customer_signed_date",
            "sow_manager_signature", "sow_manager_full_name",
            "sow_manager_signed_date",
        ):
            tab = self.result["tabs"][key]
            self.assertEqual(tab["documentId"], "1")
            self.assertEqual(tab["pageNumber"], "2")

    def test_customer_reason_is_in_expedited_document(self):
        tab = self.result["tabs"]["expedited_customer_reason"]
        self.assertEqual(tab["documentId"], "2")
        self.assertEqual(tab["pageNumber"], "1")

    def test_manager_and_comptroller_are_separate(self):
        a = self.result["tabs"]["expedited_manager_initials"]
        b = self.result["tabs"]["expedited_comptroller_initials"]
        self.assertNotEqual(a["yPosition"], b["yPosition"])

    def test_original_four_positions_remain_available(self):
        for key in (
            "sow_proposed_date", "sow_customer_initials",
            "expedited_requested_date",
            "expedited_customer_signature",
        ):
            self.assertIn(key, self.result["tabs"])

    def test_all_authority_flags_remain_false(self):
        for key in (
            "provider_verified", "send_authorized",
            "signatures_verified", "independent_reviews_verified",
            "distribution_verified", "installation_authorized",
        ):
            self.assertIs(self.result[key], False)

    def test_visual_approval_still_required(self):
        self.assertTrue(self.result["visual_approval_required"])
        self.assertIn("VISUAL_APPROVAL_PENDING", self.result["status"])
