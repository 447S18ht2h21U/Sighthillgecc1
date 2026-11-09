"""Unregistered fail-closed completion authorization guard."""
from rest_framework.exceptions import PermissionDenied, ValidationError
from .project_completion_preflight import assess_project_completion_preflight


def require_verified_project_completion(*, actor, project_id):
    report = assess_project_completion_preflight(
        actor=actor, project_id=project_id
    )

    if (
        report.completion_authorized
        or report.project_completed
        or report.receipt_email_authenticated
        or report.docusign_completion_authenticated
    ):
        raise ValidationError(
            "Untrusted completion evidence cannot authorize a project."
        )

    raise PermissionDenied(
        "Project completion remains unavailable until the exact final "
        "Receipt is retained and its customer email sending is verified, "
        "and GECC has received and retained an independently verified "
        "completed DocuSign Completion Certificate. "
        "Customer Satisfaction Survey is optional."
    )