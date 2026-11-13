"""Read-only completion evidence requirements for authorized reviewers.

Candidate documents and local observations are never proof of provider
authenticity, customer email sending, or completion authority.
"""
from .models import Project


def completion_evidence_requirements(project, report=None):
    if not isinstance(project, Project):
        raise TypeError("A persisted project is required.")

    msr = project.current_approved
    msr_ready = (
        project.state != "CANCELLED"
        and msr is not None
        and msr.status == "APPROVED"
        and msr.project_id == project.pk
    )

    def count(name):
        value = getattr(report, name, 0) if report is not None else 0
        if type(value) is not int or value < 0:
            raise ValueError("Invalid completion evidence candidate count.")
        return value

    receipt_count = count("receipt_candidates")
    email_count = count("unverified_email_observations")
    certificate_count = count("certificate_candidates")

    return [
        {
            "key": "approved_msr",
            "label": "Current approved Master Sales Record",
            "status": "READY" if msr_ready else "BLOCKED",
            "candidate_count": 0,
            "detail": (
                "The current approved MSR is present."
                if msr_ready
                else "An approved MSR for an active project is required."
            ),
        },
        {
            "key": "final_receipt",
            "label": "Exact final Receipt PDF",
            "status": "BLOCKED",
            "candidate_count": receipt_count,
            "detail": (
                "Historical PDF candidates do not establish the "
                "final customer Receipt or its immutable version."
            ),
        },
        {
            "key": "receipt_email",
            "label": "Authenticated customer Receipt email sending",
            "status": "BLOCKED",
            "candidate_count": email_count,
            "detail": (
                "Test dispatch and local observations do not prove "
                "provider-authenticated sending to the approved customer."
            ),
        },
        {
            "key": "completion_certificate",
            "label": "Verified completed DocuSign Completion Certificate",
            "status": "BLOCKED",
            "candidate_count": certificate_count,
            "detail": (
                "A matching local envelope and PDF are not independent "
                "DocuSign confirmation of signatures and GECC receipt."
            ),
        },
        {
            "key": "completion_transaction",
            "label": "Authorized project-completion transaction",
            "status": "BLOCKED",
            "candidate_count": 0,
            "detail": (
                "Project completion remains disabled until all "
                "mandatory evidence and authority checks are implemented."
            ),
        },
    ]
