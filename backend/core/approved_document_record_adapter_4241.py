"""Authorized, read-only document review of already-loaded records.

Not an API, document renderer, signing operation, approval, or release.
No queries or database writes are performed by this adapter.
"""
from dataclasses import dataclass

from .approved_document_msr_binding_4240 import (
    inspect_approved_msr_binding,
)


class DocumentReviewDenied(ValueError):
    """The requested document review is not eligible."""


@dataclass(frozen=True)
class DocumentRecordReview:
    project_id: str
    msr_id: str
    version: int
    snapshot_sha256: str
    financing_type: str
    review_only: bool = True
    release_authorized: bool = False


def inspect_authorized_document_record(*, actor, project, msr):
    """Require existing authorization and current approved MSR identity."""
    if actor is None or project is None or msr is None:
        raise DocumentReviewDenied(
            "Actor, project, and approved MSR are required."
        )

    # Use the same authorization requirement as existing document generation.
    # Authorization exceptions propagate and fail closed.
    from .services import authorize
    authorize(actor, project, approval=True)

    binding = inspect_approved_msr_binding(project, msr)

    return DocumentRecordReview(
        project_id=binding.project_id,
        msr_id=binding.msr_id,
        version=binding.version,
        snapshot_sha256=binding.snapshot_sha256,
        financing_type=msr.snapshot["financing_type"],
    )