"""Read-only project checklist from a verified fictional document review.

This does not inspect real payment, signature, installation or delivery
evidence. Those remain unverified until their own services establish them.
No routes, database queries, writes, release or completion authority.
"""
from dataclasses import dataclass

from .approved_document_version_lock_4250 import (
    inspect_version_locked_review,
)


@dataclass(frozen=True)
class WorkflowChecklistItem:
    code: str
    title: str
    status: str
    explanation: str


@dataclass(frozen=True)
class ProjectWorkflowChecklist:
    project_id: str
    msr_id: str
    msr_version: int
    document_count: int
    items: tuple[WorkflowChecklistItem, ...]
    review_only: bool = True
    installation_authorized: bool = False
    project_completion_authorized: bool = False


def inspect_project_workflow_checklist(*, project, msr, batch):
    """Describe verified previews without claiming later-stage evidence."""
    lifecycle = inspect_version_locked_review(
        project=project, msr=msr, batch=batch,
    )

    if (
        lifecycle.review_only is not True
        or lifecycle.installation_authorized is not False
        or lifecycle.project_completion_authorized is not False
        or len(lifecycle.documents) != 6
        or any(not item.preview_verified for item in lifecycle.documents)
    ):
        raise ValueError("Incomplete or operational document lifecycle.")

    items = (
        WorkflowChecklistItem(
            "MSR_BINDING", "Approved MSR binding",
            "VERIFIED",
            "Current approved version and snapshot fingerprint matched.",
        ),
        WorkflowChecklistItem(
            "PDF_PREVIEWS", "Six document previews",
            "VERIFIED_REVIEW_ONLY",
            "Six PDF contents, fingerprints and page counts verified.",
        ),
        WorkflowChecklistItem(
            "CONTRACT_PAYMENT", "Contract and payment evidence",
            "NOT_EVALUATED",
            "Signature, payment, cancellation and waiting-period controls "
            "require independent checks.",
        ),
        WorkflowChecklistItem(
            "INSTALLATION", "Installation-stage evidence",
            "NOT_EVALUATED",
            "Scheduling, physical equipment identification and serial "
            "number requirements remain separate.",
        ),
        WorkflowChecklistItem(
            "FINAL_INVOICE", "Final Invoice and delivery",
            "NOT_EVALUATED",
            "Final equipment records, invoice version and customer "
            "delivery require separate evidence.",
        ),
        WorkflowChecklistItem(
            "COMPLETION", "Final Receipt and DocuSign completion",
            "NOT_EVALUATED",
            "Retained final Receipt, verified customer email and completed "
            "project-specific DocuSign certificate require trusted evidence.",
        ),
    )

    return ProjectWorkflowChecklist(
        project_id=str(project.pk),
        msr_id=str(msr.pk),
        msr_version=msr.number,
        document_count=len(lifecycle.documents),
        items=items,
    )