"""Unregistered, read-only administrative completion preflight.

This module never transitions a Project, authenticates a provider,
sends email, or accepts candidate records as trusted proof.
"""
from dataclasses import dataclass

from rest_framework.exceptions import PermissionDenied, ValidationError

from .completion_evidence_provenance_report import (
    inspect_completion_provenance,
)
from .models import Project, User
from .services import authorize


@dataclass(frozen=True)
class ProjectCompletionPreflight:
    project_id: str
    current_approved_msr_id: str
    receipt_candidates: int
    unverified_email_observations: int
    certificate_candidates: int
    receipt_email_authenticated: bool
    docusign_completion_authenticated: bool
    satisfaction_survey_required: bool
    blockers: tuple[str, ...]
    completion_authorized: bool = False
    project_completed: bool = False


def assess_project_completion_preflight(*, actor, project_id):
    """Check existing authorization before inspecting evidence.

    Both evidence classes remain untrusted until future independently
    authenticated, immutable, project-bound verification is operational.
    """
    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("Authenticated project approver required.")

    fresh_actor = User.objects.get(pk=actor.pk)
    if not fresh_actor.is_active:
        raise PermissionDenied("Active project approver required.")

    project = (
        Project.objects
        .select_related("current_approved")
        .get(pk=project_id)
    )

    # Reuse the existing approval authorization boundary.
    authorize(fresh_actor, project, approval=True)

    if project.state == "CANCELLED":
        raise ValidationError("Cancelled project cannot be completed.")

    msr = project.current_approved
    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
    ):
        raise ValidationError("Current project-approved MSR required.")

    report = inspect_completion_provenance(
        project_id=str(project.pk)
    )

    if report.approved_msr_id != str(msr.pk):
        raise ValidationError("Completion evidence MSR binding mismatch.")

    blockers = list(report.blockers)

    # Missing authenticated provider evidence must remain a blocker
    # even if locally stored PDF or observation counts are positive.
    if not report.trusted_receipt_email:
        blockers.append(
            "Authenticated sending proof for the exact final "
            "customer Receipt is required."
        )
    if not report.trusted_completed_docusign:
        blockers.append(
            "Authenticated completed DocuSign certificate, "
            "GECC receipt and retained PDF are required."
        )

    blockers.append(
        "The authorized project-completion transaction "
        "has not been implemented."
    )

    return ProjectCompletionPreflight(
        project_id=str(project.pk),
        current_approved_msr_id=str(msr.pk),
        receipt_candidates=report.receipt_pdf_candidates,
        unverified_email_observations=report.synthetic_email_observations,
        certificate_candidates=report.envelope_bound_certificate_candidates,
        receipt_email_authenticated=False,
        docusign_completion_authenticated=False,
        satisfaction_survey_required=False,
        blockers=tuple(blockers),
    )