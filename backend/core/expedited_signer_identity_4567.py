"""Development-only read of trusted customer signing identity.

An existing COMMERCIAL customer-signer authorization identifies the
approved customer for the current MSR. It does NOT authorize the
separate expedited-service workflow or grant signing/send permission.
"""
from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import CustomerSignerAuthorization, Project
from .customer_signer_authorization_services import (
    verify_customer_signer_integrity,
)
from .expedited_signing_preflight_4567 import (
    assess_unified_signing_preflight,
)


def assess_expedited_customer_identity(*, actor, project_id):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Customer identity assessment is not live-enabled.")

    preflight = assess_unified_signing_preflight(
        actor=actor, project_id=project_id,
    )

    if (
        type(preflight) is not dict
        or preflight.get("administrative_chain_reviewed") is not True
        or preflight.get("send_authorized") is not False
        or preflight.get("installation_authorized") is not False
    ):
        raise ValidationError("Protected administrative preflight failed.")

    project = Project.objects.select_related(
        "current_approved", "customer"
    ).filter(pk=preflight["project_id"]).first()

    if (
        project is None or project.state == "CANCELLED"
        or project.current_approved_id is None
        or str(project.current_approved_id) != preflight["msr_id"]
        or project.current_approved is None
        or project.current_approved.status != "APPROVED"
        or project.current_approved.number != preflight["msr_version"]
        or project.customer_id is None
        or project.customer is None
        or project.customer.archived is True
    ):
        raise ValidationError("Current project/customer identity mismatch.")

    # Reuse the approved commercial customer identity as a reference,
    # never as an expedited signing authorization.
    approvals = list(
        CustomerSignerAuthorization.objects.filter(
            project_id=project.pk,
            approved_msr_id=project.current_approved_id,
            customer_id=project.customer_id,
            group=CustomerSignerAuthorization.Group.COMMERCIAL,
            revocation__isnull=True,
        )[:2]
    )

    if len(approvals) != 1:
        raise ValidationError(
            "Exactly one active commercial customer-signer approval required."
        )

    approval = approvals[0]
    if (
        approval.project_id != project.pk
        or approval.approved_msr_id != project.current_approved_id
        or approval.customer_id != project.customer_id
        or approval.group != CustomerSignerAuthorization.Group.COMMERCIAL
        or not approval.signer_name.strip()
        or not approval.signer_email.strip()
    ):
        raise ValidationError("Customer-signer authorization does not match.")

    # This existing service independently verifies the immutable digest
    # and exact matching audit event; do not replace it with a flag.
    checked = verify_customer_signer_integrity(approval)
    if checked is None or checked.pk != approval.pk:
        raise ValidationError("Customer-signer audit verification failed.")

    return {
        "status": "CUSTOMER_IDENTITY_BOUND_EXPEDITED_SCOPE_PENDING",
        "project_id": preflight["project_id"],
        "msr_id": preflight["msr_id"],
        "msr_version": preflight["msr_version"],
        "snapshot_sha256": preflight["snapshot_sha256"],
        "proposed_date": preflight["proposed_date"],
        "commercial_signer_authorization_id": str(approval.pk),
        "commercial_signer_authorization_digest": approval.digest,
        "customer_signer_name": approval.signer_name,
        "customer_signer_email": approval.signer_email,
        "expedited_signer_authorized": False,
        "recipient_routing_verified": False,
        "signed_documents_retained": False,
        "send_authorized": False,
        "installation_authorized": False,
    }
