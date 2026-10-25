"""Completion envelope attempt prerequisites; no provider calls or sending."""

from django.db import transaction
from uuid import UUID
from rest_framework.exceptions import ValidationError
from .models import CompletionEnvelopeAttempt, Project, ReleasePackage
from .services import audit
from .completion_signature_eligibility import require_verification_eligibility


def require_attempt_eligibility(actor, package):
    """Check approval, Comptroller authority and project-level attempt conflicts."""
    result = require_verification_eligibility(actor, package)
    project_id = package.plan.msr.project_id
    existing = CompletionEnvelopeAttempt.objects.filter(
        release_package__plan__msr__project_id=project_id,
        release_package__plan__group__in=("COMPLETION_FINANCED", "COMPLETION_NON_FINANCED"),
    )
    if existing.exists():
        raise ValidationError("A completion envelope attempt already exists for this project. Review its outcome before proceeding.")
    return {**result, "attempt_creation_eligible": True, "provider_authenticated": False, "send_available": False}

@transaction.atomic
def create_attempt(actor, package_id, provider_account_id):
    """Record a guarded attempt. Never contact DocuSign or send documents."""
    try:
        account_id = str(UUID(provider_account_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("A valid provider account UUID is required.") from None
    if provider_account_id != account_id:
        raise ValidationError("Provider account UUID must use canonical form.")
    reference = ReleasePackage.objects.select_related("plan__msr").get(pk=package_id)
    project_id = reference.plan.msr.project_id
    Project.objects.select_for_update().get(pk=project_id)
    package = ReleasePackage.objects.select_related("plan__msr__project").get(pk=package_id)
    require_attempt_eligibility(actor, package)
    attempt = CompletionEnvelopeAttempt.objects.create(
        release_package=package, initiated_by=actor, provider_account_id=account_id)
    audit(actor, "completion_envelope.attempt_created", project_id, {
        "attempt_id": str(attempt.pk), "release_package_id": str(package.pk),
        "release_package_digest": package.digest, "provider_account_id": account_id,
        "state": attempt.state,
    })
    return attempt
