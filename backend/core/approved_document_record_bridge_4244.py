"""Development-only bridge from an authorized MSR to fictional previews.

This module has no API registration, database writes, signing, dispatch,
document persistence, or production release authority.
"""
from copy import deepcopy
from dataclasses import dataclass

from .approved_document_record_adapter_4241 import (
    inspect_authorized_document_record,
)
from .approved_six_document_batch_4236 import (
    build_six_document_review,
)


class BridgeDenied(ValueError):
    """A real customer or unsafe review request was supplied."""


@dataclass(frozen=True)
class DocumentBridgeReview:
    project_id: str
    msr_id: str
    version: int
    snapshot_sha256: str
    financing_type: str
    review_only: bool = True
    release_authorized: bool = False


def prepare_fictional_document_review(
    *, actor, project, msr, directory, created, associate,
    invoice_number, invoice_date,
):
    """Review an approved fictional MSR without operational side effects."""

    # The existing operational permission service is authoritative.
    record = inspect_authorized_document_record(
        actor=actor, project=project, msr=msr
    )

    snapshot = deepcopy(msr.snapshot)
    customer = snapshot.get("customer")

    if (
        type(customer) is not str
        or "FICTIONAL" not in customer.upper()
    ):
        raise BridgeDenied(
            "Only explicitly fictional MSR records may enter this bridge."
        )

    project_code = getattr(project, "code", None)
    if type(project_code) is not str or not project_code.strip():
        raise BridgeDenied("Project code is required.")

    batch = build_six_document_review(
        directory,
        snapshot,
        project_code=project_code,
        msr_version=str(record.version),
        created=created,
        associate=associate,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
    )

    if (
        batch.get("signed") is not False
        or batch.get("released") is not False
        or batch.get("customer_delivery") is not False
    ):
        raise BridgeDenied("Operational document state is prohibited.")

    review = DocumentBridgeReview(
        project_id=record.project_id,
        msr_id=record.msr_id,
        version=record.version,
        snapshot_sha256=record.snapshot_sha256,
        financing_type=record.financing_type,
    )

    return {
        "record": review,
        "manifest": batch["manifest"],
        "pdfs": batch["pdfs"],
        "review_only": True,
        "release_authorized": False,
    }