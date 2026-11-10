from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from .expedited_reviewer_choices_4567 import (
    REVIEWERS,
    reviewer_choice_candidate,
    validate_review_choice,
)

ROOT = (
    Path(settings.BASE_DIR).parent
    / "docs/reference/GECC-20261107-final-seven"
)


class ExpeditedReviewerChoice4567Tests(SimpleTestCase):
    def test_both_reviewers_have_five_separate_controls(self):
        candidate = reviewer_choice_candidate(ROOT)
        self.assertEqual(set(candidate["reviewer_controls"]), set(REVIEWERS))
        for role in REVIEWERS:
            self.assertEqual(
                set(candidate["reviewer_controls"][role]),
                {
                    "approve", "reject", "approve_initials",
                    "reject_initials", "date",
                },
            )

    def test_reviewer_choices_are_spatially_separate(self):
        candidate = reviewer_choice_candidate(ROOT)
        for controls in candidate["reviewer_controls"].values():
            self.assertNotEqual(
                controls["approve"]["xPosition"],
                controls["reject"]["xPosition"],
            )
            self.assertNotEqual(
                controls["approve_initials"]["xPosition"],
                controls["reject_initials"]["xPosition"],
            )

    def test_review_candidate_never_grants_authority(self):
        result = reviewer_choice_candidate(ROOT)
        self.assertFalse(result["controls_visually_approved"])
        self.assertFalse(result["send_authorized"])
        self.assertFalse(result["independent_reviews_verified"])
        self.assertFalse(result["installation_authorized"])

    def test_approve_with_matching_initials(self):
        result = validate_review_choice(
            approved=True, rejected=False,
            approved_initialed=True, rejected_initialed=False,
            signed_date="2026-11-09",
        )
        self.assertEqual(result["candidate_decision"], "APPROVED")
        self.assertFalse(result["independent_review_verified"])

    def test_reject_with_matching_initials(self):
        result = validate_review_choice(
            approved=False, rejected=True,
            approved_initialed=False, rejected_initialed=True,
            signed_date="2026-11-09",
        )
        self.assertEqual(result["candidate_decision"], "REJECTED")
        self.assertFalse(result["installation_authorized"])

    def test_neither_choice_is_invalid(self):
        with self.assertRaises(ValueError):
            validate_review_choice(
                approved=False, rejected=False,
                approved_initialed=False, rejected_initialed=False,
                signed_date="2026-11-09",
            )

    def test_both_choices_are_invalid(self):
        with self.assertRaises(ValueError):
            validate_review_choice(
                approved=True, rejected=True,
                approved_initialed=True, rejected_initialed=True,
                signed_date="2026-11-09",
            )

    def test_initials_must_match_selected_choice(self):
        with self.assertRaises(ValueError):
            validate_review_choice(
                approved=True, rejected=False,
                approved_initialed=False, rejected_initialed=True,
                signed_date="2026-11-09",
            )

    def test_review_date_is_required(self):
        with self.assertRaises(ValueError):
            validate_review_choice(
                approved=True, rejected=False,
                approved_initialed=True, rejected_initialed=False,
                signed_date="",
            )

    def test_choice_must_be_boolean(self):
        with self.assertRaises(ValueError):
            validate_review_choice(
                approved="yes", rejected=False,
                approved_initialed=True, rejected_initialed=False,
                signed_date="2026-11-09",
            )
