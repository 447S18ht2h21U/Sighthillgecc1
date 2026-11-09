"""Unregistered database-backed preview of approved pre-installation policy.

Read-only and fail-closed. Does not grant installation authority.
Live scheduling, eligibility, dashboard and signing remain unchanged.
"""
from dataclasses import dataclass

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .installation_eligibility import (
    cancellation_deadline,
    require_current_approved_msr,
    verified_signature_time,
)
from .installation_payment_readiness import installation_payment_readiness
from .installation_waiting_period_policy import assess_waiting_period
from .models import CustomerSignatureEvidence


@dataclass(frozen=True)
class PreInstallationPreview:
    msr_id: str | None
    requirements_satisfied: bool
    blockers: tuple[str, ...]
    installation_authorized: bool = False
    invoice_delivery_verified: bool = False


def preview_pre_installation(project, *, now=None):
    """Inspect existing independently recorded evidence without writing."""
    blockers = []
    msr = None
    contract_time = None
    deadline = None

    current = timezone.now() if now is None else now

    if project.state == "CANCELLED":
        blockers.append("Project is cancelled.")

    try:
        msr = require_current_approved_msr(project)
        if msr.project_id != project.pk:
            raise ValidationError("Approved MSR belongs to another project.")
    except ValidationError:
        blockers.append("Current approved MSR is required.")

    if msr is not None:
        try:
            contract_time = verified_signature_time(
                msr, CustomerSignatureEvidence.DocumentKind.CONTRACT
            )
        except (ValidationError, ValueError, TypeError):
            blockers.append("Verified customer Contract signature is required.")

        try:
            deadline = cancellation_deadline(msr)
        except (ValidationError, ValueError, TypeError):
            blockers.append("Verified cancellation deadline is required.")

        if contract_time is not None and deadline is not None:
            try:
                waiting = assess_waiting_period(
                    verified_contract_signed_at=contract_time,
                    verified_cancellation_deadline=deadline,
                    now=current,
                )
                if not waiting.ready:
                    blockers.append(
                        "Five-day waiting period or cancellation deadline remains open."
                    )
            except (ValueError, OverflowError, TypeError):
                blockers.append("Waiting-period timestamps are invalid.")

        try:
            payment = installation_payment_readiness(project)
            if payment.get("payment_ready") is not True:
                blockers.append(
                    str(payment.get("explanation") or "Required payment is not verified.")
                )
        except (ValidationError, ValueError, TypeError):
            blockers.append("Required payment evidence is invalid or missing.")

    return PreInstallationPreview(
        msr_id=str(msr.pk) if msr is not None else None,
        requirements_satisfied=not blockers,
        blockers=tuple(blockers),
    )