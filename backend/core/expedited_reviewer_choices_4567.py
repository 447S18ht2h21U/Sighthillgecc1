"""Explicit conditional reviewer-choice candidate positions.

This module does not send DocuSign envelopes, create decisions, or verify
signatures. Coordinates still require visual confirmation.
"""
from datetime import date

from .expedited_signing_remaining_layout_4567 import (
    complete_visual_candidate,
)

REVIEWERS = ("INSTALLATION_MANAGER", "COMPTROLLER")

# x, top, width, height: candidate rectangles measured in PDF points.
# Approved and rejected initials must be different tabs, because the
# printed form has a separate initials space beneath each decision.
REVIEW_REGIONS = {'INSTALLATION_MANAGER': {'approve': (256, 625, 18, 16),
                          'reject': (364, 625, 18, 16),
                          'approve_initials': (260, 649, 52, 10),
                          'reject_initials': (363, 649, 52, 10),
                          'date': (109, 649, 120, 17)},
 'COMPTROLLER': {'approve': (256, 677, 18, 16),
                 'reject': (364, 677, 18, 16),
                 'approve_initials': (260, 701, 52, 9),
                 'reject_initials': (363, 701, 52, 9),
                 'date': (109, 701, 120, 17)}}


def reviewer_choice_candidate(reference_root):
    base = complete_visual_candidate(reference_root)
    controls = {}

    for role, regions in REVIEW_REGIONS.items():
        controls[role] = {}
        for key, (x, y, width, height) in regions.items():
            if (
                min(x, y) < 0 or min(width, height) <= 0
                or x + width > 612 or y + height > 792
            ):
                raise ValueError("Review control is outside approved PDF.")

            controls[role][key] = {
                "documentId": "2",
                "pageNumber": "1",
                "xPosition": str(x),
                "yPosition": str(y),
                "width": str(width),
                "height": str(height),
                "tabLabel": f"{role.lower()}-{key.replace('_', '-')}",
                "visually_approved": False,
            }

    return {
        "status": "REVIEW_CONTROL_VISUAL_CONFIRMATION_PENDING",
        "source_document_sha256": base["documents"][
            "EXPEDITED_SERVICE"
        ]["sha256"],
        "reviewer_controls": controls,
        "decision_rule": "EXACTLY_ONE_OF_APPROVE_OR_REJECT",
        "selected_decision_initials_required": True,
        "decision_date_required": True,
        "customer_completion_required_first": True,
        "independent_reviewers_required": True,
        "controls_visually_approved": False,
        "send_authorized": False,
        "independent_reviews_verified": False,
        "installation_authorized": False,
    }


def validate_review_choice(
    *, approved, rejected, approved_initialed,
    rejected_initialed, signed_date,
):
    """Structural decision check, NOT authenticated reviewer evidence."""
    if any(
        type(value) is not bool
        for value in (
            approved, rejected, approved_initialed, rejected_initialed
        )
    ):
        raise ValueError("Explicit Boolean review choices required.")

    if approved == rejected:
        raise ValueError("Select exactly one review decision.")

    if approved_initialed != approved or rejected_initialed != rejected:
        raise ValueError("Only the selected decision must be initialed.")

    if type(signed_date) is not str:
        raise ValueError("A review date is required.")

    try:
        parsed = date.fromisoformat(signed_date)
    except ValueError:
        raise ValueError("Invalid review date.") from None

    if parsed.isoformat() != signed_date:
        raise ValueError("Noncanonical review date.")

    return {
        "candidate_decision": "APPROVED" if approved else "REJECTED",
        "reviewer_authenticated": False,
        "independent_review_verified": False,
        "installation_authorized": False,
    }
