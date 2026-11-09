"""Read-only six-document lifecycle inventory.

A fictional PDF review is never evidence of signing, payment,
customer delivery, or completion. No ORM, API, or file writes.
"""
from dataclasses import dataclass

from .approved_document_compatibility_4247 import (
    describe_compatibility,
)
from .approved_six_document_batch_4236 import KINDS


class LifecycleDenied(ValueError):
    """The supplied preview cannot establish lifecycle readiness."""


@dataclass(frozen=True)
class DocumentLifecycleItem:
    kind: str
    legacy_kind: str | None
    preview_verified: bool
    operational_document_verified: bool = False
    signed_evidence_verified: bool = False
    customer_delivery_verified: bool = False
    completion_evidence_verified: bool = False


@dataclass(frozen=True)
class DocumentLifecycleReview:
    documents: tuple[DocumentLifecycleItem, ...]
    review_only: bool = True
    installation_authorized: bool = False
    project_completion_authorized: bool = False


def inspect_fictional_document_lifecycle(batch):
    """Classify six verified previews without promoting them to evidence."""
    if type(batch) is not dict:
        raise LifecycleDenied("A fictional review batch is required.")

    if (
        batch.get("review_only") is not True
        or batch.get("release_authorized") is not False
    ):
        raise LifecycleDenied("Operational review state is prohibited.")

    record = batch.get("record")
    if (
        record is None
        or getattr(record, "review_only", None) is not True
        or getattr(record, "release_authorized", None) is not False
    ):
        raise LifecycleDenied("Review-only MSR binding is required.")

    manifest = batch.get("manifest")
    pdfs = batch.get("pdfs")

    if type(manifest) not in (tuple, list) or type(pdfs) is not dict:
        raise LifecycleDenied("Complete PDF review evidence is required.")

    if len(manifest) != len(KINDS) or set(pdfs) != set(KINDS):
        raise LifecycleDenied("Six distinct approved previews are required.")

    if len(pdfs) != 6 or any(
        type(pdfs[kind]) is not bytes or not pdfs[kind]
        for kind in KINDS
    ):
        raise LifecycleDenied("Verified PDF content is missing.")

    found = []
    for index, kind in enumerate(KINDS):
        entry = manifest[index]
        if (
            type(entry) is not dict
            or entry.get("kind") != kind
            or entry.get("status") != "FICTIONAL_REVIEW_ONLY"
        ):
            raise LifecycleDenied("Document manifest identity mismatch.")
        found.append(
            DocumentLifecycleItem(
                kind=kind,
                legacy_kind=describe_compatibility(kind).legacy_kind,
                preview_verified=True,
            )
        )

    return DocumentLifecycleReview(documents=tuple(found))