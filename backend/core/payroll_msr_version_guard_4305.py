"""Test-only conservative MSR version safeguard for payroll candidates.

This wrapper refuses historical approved-version ambiguity, inconsistent
payment MSR references, and mismatched project ownership.

Draft revisions are not approved financial history. This is intentionally
more restrictive than an eventual version-aware historical resolver.

A passing candidate is NOT an approved earning date, payroll permission,
or proof that the underlying audit chain has been fully validated.
Never register this as a live API.
"""
from .models import ContractorPaymentRecord, CustomerPayment, MSR, Project
from .payroll_technical_provenance_4296 import _uuid
from .payroll_earned_technical_candidate_4304 import (
    candidate_earned_technical_payment,
)


def candidate_version_guarded_technical_payment(*, payment_id):
    identifier = _uuid(payment_id)
    if identifier is None:
        return None

    record = ContractorPaymentRecord.objects.filter(
        pk=identifier
    ).first()
    if record is None or record.project_id is None:
        return None

    project = Project.objects.select_related(
        "current_approved"
    ).filter(pk=record.project_id).first()

    if project is None or project.current_approved_id is None:
        return None

    approved = project.current_approved
    if approved.status != "APPROVED":
        return None
    if approved.project_id != project.pk:
        return None

    if MSR.objects.filter(
        project_id=project.pk,
        status="APPROVED",
    ).count() != 1:
        return None

    # A historical non-draft version needs an actual version-aware
    # earning-date review, even if it is no longer the current version.
    if MSR.objects.filter(
        project_id=project.pk
    ).exclude(
        pk=approved.pk
    ).exclude(
        status="DRAFT"
    ).exists():
        return None

    # Even a pending receipt referencing another MSR must not be silently
    # included in an interpretation of the current approved version.
    if CustomerPayment.objects.filter(
        project_id=project.pk
    ).exclude(
        msr_id=approved.pk
    ).exists():
        return None

    candidate = candidate_earned_technical_payment(
        payment_id=record.pk
    )
    if candidate is None:
        return None
    if candidate.get("project_id") != str(project.pk):
        return None
    if candidate.get("status") != "TEST_ONLY_UNAPPROVED_CANDIDATE":
        return None

    return candidate


def msr_version_guard_grants_live_access(*args, **kwargs):
    return False