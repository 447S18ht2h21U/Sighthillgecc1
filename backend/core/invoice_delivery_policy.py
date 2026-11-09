"""VERIDIAN Invoice delivery evidence policy foundation.

Pure, unregistered policy definitions. This module never sends a document,
writes a record, changes installation eligibility, or grants authority.

Important: an approved MSR, generated PDF, approved release-review package,
download, and sandbox test are NOT verified customer delivery.
"""

from dataclasses import dataclass
from enum import Enum


class InvoiceDeliveryState(str, Enum):
    NOT_PREPARED = "NOT_PREPARED"
    PREPARATION_ONLY = "PREPARATION_ONLY"
    RELEASE_REVIEW_APPROVED = "RELEASE_REVIEW_APPROVED"
    DELIVERY_UNVERIFIED = "DELIVERY_UNVERIFIED"
    DELIVERY_VERIFIED = "DELIVERY_VERIFIED"


@dataclass(frozen=True)
class InvoiceDeliveryAssessment:
    state: InvoiceDeliveryState
    installation_evidence_accepted: bool
    explanation: str


def assess_existing_invoice_evidence(
    *,
    document_generated: bool = False,
    release_review_approved: bool = False,
    delivery_claimed: bool = False,
) -> InvoiceDeliveryAssessment:
    """Classify current workflow evidence without asserting customer delivery.

    Current VERIDIAN workflows do not yet provide an independently
    verified, immutable, MSR-bound customer delivery receipt.

    Every state returned here is therefore ineligible for use as
    installation delivery evidence. The DELIVERY_VERIFIED enum is reserved
    for a future separately approved trusted-evidence integration.
    """
    for name, value in (
        ("document_generated", document_generated),
        ("release_review_approved", release_review_approved),
        ("delivery_claimed", delivery_claimed),
    ):
        if type(value) is not bool:
            raise TypeError(f"{name} must be a Boolean.")

    if delivery_claimed:
        return InvoiceDeliveryAssessment(
            InvoiceDeliveryState.DELIVERY_UNVERIFIED,
            False,
            "A delivery claim is not independently verified customer delivery.",
        )

    if release_review_approved:
        return InvoiceDeliveryAssessment(
            InvoiceDeliveryState.RELEASE_REVIEW_APPROVED,
            False,
            "Internal release approval does not prove customer delivery.",
        )

    if document_generated:
        return InvoiceDeliveryAssessment(
            InvoiceDeliveryState.PREPARATION_ONLY,
            False,
            "A generated Invoice is a preparation copy, not delivery evidence.",
        )

    return InvoiceDeliveryAssessment(
        InvoiceDeliveryState.NOT_PREPARED,
        False,
        "No verified Invoice delivery evidence is available.",
    )