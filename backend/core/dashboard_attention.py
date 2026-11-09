"""Read-only, role-scoped projects with no earned Dashboard milestone.

No new permissions, no fabricated evidence, no project mutations.
"""
from .dashboard_services import get_project_dashboard_stages
from .operational_visibility import operational_project_scope


def get_attention_projects(actor):
    """Return only visible projects with zero independently earned stages."""
    visible = operational_project_scope(actor).select_related(
        "customer", "pending", "current_approved"
    ).order_by("-created_at", "-id")
    return [
        project for project in visible
        if not get_project_dashboard_stages(project)
    ]


def attention_hint(state):
    """Plain-language hint, never authorization or a completed milestone."""
    hints = {
        "DRAFT": ("Complete the draft MSR", "Finish the MSR and submit it for review."),
        "REVISED": ("Finish the MSR revision", "Review the changes and submit the new version."),
        "SUBMITTED": ("MSR review pending", "An authorized reviewer must evaluate the MSR."),
        "REJECTED": ("Correct the rejected MSR", "Review the rejection reason and edit the draft."),
        "APPROVED": ("Review pending project steps", "Check verified documents, installation and payment requirements."),
        "CANCELLED": ("Project cancelled", "Further work requires authorized reopening."),
    }
    if type(state) is not str:
        raise ValueError("Project state must be text.")
    label, detail = hints.get(
        state,
        ("Review project status", "Confirm the project state before taking action."),
    )
    return {"label": label, "detail": detail, "read_only": True}
