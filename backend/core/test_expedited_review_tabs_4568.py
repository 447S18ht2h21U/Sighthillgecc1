from copy import deepcopy
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .expedited_review_tabs_4568 import (
    reviewer_provider_tabs_candidate,
)

MODULE = "core.expedited_review_tabs_4568"


class ConditionalReviewerTabs4568Tests(SimpleTestCase):
    def setUp(self):
        self.candidate = reviewer_provider_tabs_candidate()
        self.reviewers = self.candidate["reviewers"]

    def test_both_reviewers_have_separate_recipients(self):
        self.assertEqual(
            [self.reviewers[k]["recipientId"] for k in (
                "INSTALLATION_MANAGER", "COMPTROLLER"
            )],
            ["2", "3"],
        )

    def test_radio_choices_are_exclusive_group_candidates(self):
        for item in self.reviewers.values():
            group, = item["radioGroupTabs"]
            self.assertEqual(group["required"], "true")
            self.assertEqual(
                {radio["value"] for radio in group["radios"]},
                {"APPROVE", "REJECT"},
            )
            self.assertTrue(all(
                radio["selected"] == "false" for radio in group["radios"]
            ))

    def test_each_initials_tab_depends_on_selected_choice(self):
        for item in self.reviewers.values():
            group, = item["radioGroupTabs"]
            self.assertEqual(
                {tab["conditionalParentValue"]
                 for tab in item["initialHereTabs"]},
                {"APPROVE", "REJECT"},
            )
            self.assertTrue(all(
                tab["conditionalParentLabel"] == group["groupName"]
                and tab["optional"] == "false"
                for tab in item["initialHereTabs"]
            ))

    def test_dates_are_provider_generated(self):
        for item in self.reviewers.values():
            signed, = item["dateSignedTabs"]
            self.assertNotIn("value", signed)
            self.assertEqual(signed["documentId"], "2")
        self.assertEqual(
            self.candidate["date_signed_source"],
            "DOCUSIGN_PROVIDER_ONLY",
        )

    def test_original_approved_locations_are_used(self):
        self.assertEqual(
            self.reviewers["INSTALLATION_MANAGER"]["initialHereTabs"][0][
                "yPosition"
            ], "649"
        )
        self.assertEqual(
            self.reviewers["COMPTROLLER"]["initialHereTabs"][0][
                "yPosition"
            ], "701"
        )

    def test_reviewer_region_outside_pdf_rejected(self):
        from .expedited_reviewer_choices_4567 import REVIEW_REGIONS
        invalid = deepcopy(REVIEW_REGIONS)
        invalid["COMPTROLLER"]["date"] = (109, 800, 120, 17)
        with patch(f"{MODULE}.REVIEW_REGIONS", invalid):
            with self.assertRaises(ValidationError):
                reviewer_provider_tabs_candidate()

    def test_missing_reviewer_control_rejected(self):
        from .expedited_reviewer_choices_4567 import REVIEW_REGIONS
        invalid = deepcopy(REVIEW_REGIONS)
        del invalid["INSTALLATION_MANAGER"]["reject_initials"]
        with patch(f"{MODULE}.REVIEW_REGIONS", invalid):
            with self.assertRaises(ValidationError):
                reviewer_provider_tabs_candidate()

    def test_nothing_is_preapproved_or_sendable(self):
        self.assertFalse(self.candidate["provider_behavior_verified"])
        self.assertFalse(self.candidate["send_authorized"])
        self.assertFalse(self.candidate["installation_authorized"])
