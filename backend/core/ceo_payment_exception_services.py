"""Controlled CEO exceptions to the standard customer deposit requirement."""

from django.db import models, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import CEOPaymentException, MSR, Project, Role
from .services import audit


def _require_active_ceo(actor):
    if actor is None or not actor.is_active or actor.role != Role.CEO:
        raise PermissionDenied("Only an active CEO may make this decision.")


def _require_reason(value):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("A written reason is required.")
    return value.strip()


def _require_current_approved(project, msr):
    if project.state == "CANCELLED":
        raise ValidationError("Cancelled projects cannot receive payment exceptions.")
    if (
        project.current_approved_id != msr.pk
        or msr.project_id != project.pk
        or msr.status != "APPROVED"
    ):
        raise ValidationError(
            "The exception must reference this project's current approved MSR."
        )


@transaction.atomic
def request_payment_exception(*, actor, project_id, msr_id, reason):
    reason = _require_reason(reason)

    if actor is None or not actor.is_active:
        raise PermissionDenied("An active requester is required.")

    project = Project.objects.select_for_update().get(pk=project_id)
    msr = MSR.objects.select_for_update().get(pk=msr_id)

    _require_current_approved(project, msr)

    if msr.snapshot.get("payment_option") != "100_PERCENT_COMPLETION":
        raise ValidationError(
            "A CEO payment exception may only be requested for an approved "
            "Master Sales Record specifying 100% payment after completion."
        )

    if project.sales_associate_id != actor.pk and project.reviewer_id != actor.pk:
        if actor.role != Role.COMPTROLLER:
            raise PermissionDenied("You cannot request an exception for this project.")

    if CEOPaymentException.objects.filter(msr=msr).exists():
        raise ValidationError("An exception request already exists for this MSR.")

    exception = CEOPaymentException.objects.create(
        project=project,
        msr=msr,
        requested_by=actor,
        request_reason=reason,
    )

    audit(
        actor,
        "CEO_PAYMENT_EXCEPTION_REQUESTED",
        exception.pk,
        {
            "project_id": str(project.pk),
            "msr_id": str(msr.pk),
            "msr_version": msr.number,
            "reason": reason,
        },
    )

    return exception


@transaction.atomic
def decide_payment_exception(*, actor, exception_id, approve, reason):
    _require_active_ceo(actor)
    reason = _require_reason(reason)

    reference = CEOPaymentException.objects.get(pk=exception_id)
    project = Project.objects.select_for_update().get(pk=reference.project_id)
    msr = MSR.objects.select_for_update().get(pk=reference.msr_id)
    exception = CEOPaymentException.objects.select_for_update().get(
        pk=exception_id
    )

    _require_current_approved(project, msr)

    if exception.project_id != project.pk or exception.msr_id != msr.pk:
        raise ValidationError("Exception project and MSR do not match.")

    if exception.requested_by_id == actor.pk:
        raise PermissionDenied("You cannot approve your own exception request.")

    if exception.status != CEOPaymentException.Status.REQUESTED:
        raise ValidationError("Only pending exceptions may be decided.")

    if msr.snapshot.get("payment_option") != "100_PERCENT_COMPLETION":
        raise ValidationError(
            "This exception requires an MSR specifying payment after completion."
        )

    exception.status = (
        CEOPaymentException.Status.APPROVED
        if approve
        else CEOPaymentException.Status.REJECTED
    )
    exception.decided_by = actor
    exception.decision_reason = reason
    exception.decided_at = timezone.now()
    exception.save(
        update_fields=[
            "status",
            "decided_by",
            "decision_reason",
            "decided_at",
        ]
    )

    audit(
        actor,
        "CEO_PAYMENT_EXCEPTION_APPROVED"
        if approve
        else "CEO_PAYMENT_EXCEPTION_REJECTED",
        exception.pk,
        {
            "project_id": str(project.pk),
            "msr_id": str(msr.pk),
            "msr_version": msr.number,
            "reason": reason,
        },
    )

    return exception


@transaction.atomic
def revoke_payment_exception(*, actor, exception_id, reason):
    _require_active_ceo(actor)
    reason = _require_reason(reason)

    reference = CEOPaymentException.objects.get(pk=exception_id)
    Project.objects.select_for_update().get(pk=reference.project_id)
    MSR.objects.select_for_update().get(pk=reference.msr_id)
    exception = CEOPaymentException.objects.select_for_update().get(
        pk=exception_id
    )

    if exception.status != CEOPaymentException.Status.APPROVED:
        raise ValidationError("Only approved exceptions may be revoked.")

    exception.status = CEOPaymentException.Status.REVOKED
    exception.revoked_by = actor
    exception.revocation_reason = reason
    exception.revoked_at = timezone.now()
    exception.save(
        update_fields=[
            "status",
            "revoked_by",
            "revocation_reason",
            "revoked_at",
        ]
    )

    audit(
        actor,
        "CEO_PAYMENT_EXCEPTION_REVOKED",
        exception.pk,
        {
            "project_id": str(exception.project_id),
            "msr_id": str(exception.msr_id),
            "reason": reason,
        },
    )

    return exception


def has_valid_payment_exception(project, msr):
    """Require a complete, current, independently approved CEO exception."""
    if project is None or msr is None:
        return False

    if (
        project.state == "CANCELLED"
        or project.current_approved_id != msr.pk
        or msr.project_id != project.pk
        or msr.status != "APPROVED"
        or msr.snapshot.get("payment_option") != "100_PERCENT_COMPLETION"
    ):
        return False

    return CEOPaymentException.objects.filter(
        project=project,
        msr=msr,
        status=CEOPaymentException.Status.APPROVED,
        decided_by__role=Role.CEO,
        decided_by__is_active=True,
        decided_at__isnull=False,
        revoked_at__isnull=True,
        revoked_by__isnull=True,
        request_reason__regex=r"\S",
        decision_reason__regex=r"\S",
    ).exclude(
        decided_by_id=models.F("requested_by_id")
    ).exists()
