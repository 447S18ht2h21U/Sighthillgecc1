"""Independent customer-signer authorization and revocation services.

Customer authority is specific to a customer, project, document group,
and signer. Approval records are immutable. Revocations are separate
immutable records. Production signing must remain fail-closed until
all provider and document-verification requirements are implemented.
"""

from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import CustomerSignerAuthorization, Role
from .operational_visibility import operational_project_scope


APPROVER_ROLES = {
    CustomerSignerAuthorization.Group.COMMERCIAL: frozenset({
        Role.SALES_MANAGER,
        Role.COMPTROLLER,
    }),
    CustomerSignerAuthorization.Group.COMPLETION_FINANCED: frozenset({
        Role.INSTALLATION_MANAGER,
        Role.COMPTROLLER,
    }),
    CustomerSignerAuthorization.Group.COMPLETION_NON_FINANCED: frozenset({
        Role.INSTALLATION_MANAGER,
        Role.COMPTROLLER,
    }),
}


def require_authorized_approver(*, approver, project, group, requested_by):
    """Validate permanent-role, project-specific, independent approval."""
    if approver is None or not approver.is_active:
        raise PermissionDenied("An active approver is required.")

    if requested_by is None or approver.pk == requested_by.pk:
        raise PermissionDenied("Independent approval is required.")

    if group not in APPROVER_ROLES:
        raise ValidationError("Unknown customer-signer document group.")

    if approver.role not in APPROVER_ROLES[group]:
        raise PermissionDenied("This role cannot approve the document group.")

    if project is None or not operational_project_scope(approver).filter(pk=project.pk).exists():
        raise PermissionDenied("Approver does not have access to this project.")

    if approver.role == Role.SALES_MANAGER:
        if project.reviewer_id != approver.pk:
            raise PermissionDenied("Sales Manager is not assigned to this project.")

    return approver

def validate_signer_evidence(
    *, project, customer, group, signer_name, signer_email,
    authority_basis, evidence_reference,
):
    """Validate required signer identity, authority, and project scope."""
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError as DjangoValidationError

    if project is None or customer is None:
        raise ValidationError("A project and customer are required.")

    if project.customer_id != customer.pk:
        raise ValidationError("Customer does not belong to this project.")

    if project.current_approved_id is None:
        raise ValidationError("An approved Master Sales Record is required.")

    if project.current_approved.status != "APPROVED":
        raise ValidationError("The Master Sales Record must be approved.")

    if group not in APPROVER_ROLES:
        raise ValidationError("Unknown customer-signer document group.")

    if group in (
        CustomerSignerAuthorization.Group.COMPLETION_FINANCED,
        CustomerSignerAuthorization.Group.COMPLETION_NON_FINANCED,
    ):
        record = project.current_approved
        if record.status != "APPROVED":
            raise ValidationError("The Master Sales Record must be approved.")

        expected_group = "COMPLETION_" + record.snapshot.get("financing_type", "")
        if group != expected_group:
            raise ValidationError(
                "Completion-certificate type does not match the approved financing classification."
            )

    required = {
        "signer_name": signer_name,
        "signer_email": signer_email,
        "authority_basis": authority_basis,
        "evidence_reference": evidence_reference,
    }

    for field, value in required.items():
        if not isinstance(value, str) or not value.strip():
            raise ValidationError({field: "This information is required."})

    if len(signer_name.strip()) > 250:
        raise ValidationError({"signer_name": "Maximum 250 characters."})

    if len(signer_email.strip()) > 254:
        raise ValidationError({"signer_email": "Maximum 254 characters."})

    try:
        validate_email(signer_email.strip())
    except DjangoValidationError:
        raise ValidationError({"signer_email": "A valid email address is required."})

    return {
        field: value.strip()
        for field, value in required.items()
    }

def approve_customer_signer(
    *, project, customer, group, signer_name, signer_email,
    authority_basis, evidence_reference, requested_by, approved_by,
):
    """Create an immutable, independently approved signer authorization."""
    import hashlib
    import json

    from django.db import transaction
    from django.utils import timezone

    from .services import audit

    if requested_by is None or not requested_by.is_active:
        raise PermissionDenied("An active requester is required.")

    with transaction.atomic():
        locked_project = (
            type(project).objects
            .select_for_update()
            .select_related("customer", "current_approved")
            .get(pk=project.pk)
        )

        require_authorized_approver(
            approver=approved_by,
            project=locked_project,
            group=group,
            requested_by=requested_by,
        )

        evidence = validate_signer_evidence(
            project=locked_project,
            customer=customer,
            group=group,
            signer_name=signer_name,
            signer_email=signer_email,
            authority_basis=authority_basis,
            evidence_reference=evidence_reference,
        )

        approved_at = timezone.now()
        payload = {
            "project_id": str(locked_project.pk),
            "customer_id": str(customer.pk),
            "approved_msr_id": str(locked_project.current_approved_id),
            "group": group,
            "requested_by_id": str(requested_by.pk),
            "approved_by_id": str(approved_by.pk),
            "approved_at": approved_at.isoformat(),
            **evidence,
        }
        digest = hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()

        authorization = CustomerSignerAuthorization.objects.create(
            project=locked_project,
            approved_msr_id=locked_project.current_approved_id,
            customer=customer,
            group=group,
            requested_by=requested_by,
            approved_by=approved_by,
            approved_at=approved_at,
            digest=digest,
            **evidence,
        )

        audit(
            approved_by,
            "CUSTOMER_SIGNER_AUTHORIZATION_APPROVED",
            authorization.pk,
            {**payload, "digest": digest},
        )

        return authorization


def require_authorized_revoker(*, revoked_by, authorization):
    """Validate permanent-role, document-group, and project-scope authority."""
    if revoked_by is None or not revoked_by.is_active:
        raise PermissionDenied("An active revoking user is required.")

    if authorization is None:
        raise ValidationError("A customer-signer authorization is required.")

    project = authorization.project

    if not operational_project_scope(revoked_by).filter(pk=project.pk).exists():
        raise PermissionDenied("Revoking user does not have access to this project.")

    if revoked_by.role == Role.COMPTROLLER:
        return revoked_by

    if revoked_by.role == Role.SALES_MANAGER:
        if authorization.group != CustomerSignerAuthorization.Group.COMMERCIAL:
            raise PermissionDenied("Sales Manager may revoke only commercial signing authority.")
        if project.reviewer_id != revoked_by.pk:
            raise PermissionDenied("Sales Manager is not assigned to this project.")
        return revoked_by

    if revoked_by.role == Role.INSTALLATION_MANAGER:
        if authorization.group not in (
            CustomerSignerAuthorization.Group.COMPLETION_FINANCED,
            CustomerSignerAuthorization.Group.COMPLETION_NON_FINANCED,
        ):
            raise PermissionDenied("Installation Manager may revoke only completion signing authority.")
        return revoked_by

    raise PermissionDenied("This role cannot revoke customer signing authority.")

def revoke_customer_signer(*, authorization_id, revoked_by, reason):
    """Revoke customer signing authority without changing its original approval."""
    import hashlib
    import json

    from django.db import transaction
    from django.utils import timezone

    from .models import CustomerSignerRevocation
    from .services import audit

    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("A documented revocation reason is required.")

    if revoked_by is None or not revoked_by.is_active:
        raise PermissionDenied("An active revoking user is required.")

    with transaction.atomic():
        authorization = (
            CustomerSignerAuthorization.objects
            .select_for_update()
            .select_related("project")
            .get(pk=authorization_id)
        )

        require_authorized_revoker(
            revoked_by=revoked_by,
            authorization=authorization,
        )

        if CustomerSignerRevocation.objects.filter(
            authorization=authorization
        ).exists():
            raise ValidationError("This authorization has already been revoked.")

        revoked_at = timezone.now()
        payload = {
            "authorization_id": str(authorization.pk),
            "project_id": str(authorization.project_id),
            "customer_id": str(authorization.customer_id),
            "group": authorization.group,
            "revoked_by_id": str(revoked_by.pk),
            "revoked_at": revoked_at.isoformat(),
            "reason": reason.strip(),
        }

        digest = hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()

        revocation = CustomerSignerRevocation.objects.create(
            authorization=authorization,
            revoked_by=revoked_by,
            revoked_at=revoked_at,
            reason=reason.strip(),
            digest=digest,
        )

        audit(
            revoked_by,
            "CUSTOMER_SIGNER_AUTHORIZATION_REVOKED",
            revocation.pk,
            {**payload, "digest": digest},
        )

        return revocation

def require_approved_customer_signer(*, msr, group, signer_name, signer_email):
    """Locate one approved, MSR-bound, non-revoked customer signer."""
    if msr is None or msr.status != "APPROVED":
        raise ValidationError("An approved Master Sales Record is required.")

    if msr.project.current_approved_id != msr.pk:
        raise ValidationError("Customer signing authority requires the current approved MSR.")

    if group not in APPROVER_ROLES:
        raise ValidationError("Unknown customer-signer document group.")

    if not isinstance(signer_name, str) or not signer_name.strip():
        raise ValidationError("An authorized customer signer name is required.")

    if not isinstance(signer_email, str) or not signer_email.strip():
        raise ValidationError("An authorized customer signer email is required.")

    matches = list(
        CustomerSignerAuthorization.objects.filter(
            approved_msr=msr,
            project_id=msr.project_id,
            customer_id=msr.project.customer_id,
            group=group,
            signer_name=signer_name.strip(),
            signer_email__iexact=signer_email.strip(),
            revocation__isnull=True,
        )[:2]
    )

    if len(matches) != 1:
        raise ValidationError(
            "Exactly one approved, non-revoked customer-signer authorization is required."
        )

    return verify_customer_signer_integrity(matches[0])

def verify_customer_signer_integrity(authorization):
    """Verify immutable approval fields, digest, and matching audit evidence."""
    import hashlib
    import hmac
    import json

    from .models import AuditEvent

    if authorization is None or authorization.approved_msr_id is None:
        raise ValidationError("Customer-signer approval evidence is incomplete.")

    payload = {
        "project_id": str(authorization.project_id),
        "customer_id": str(authorization.customer_id),
        "approved_msr_id": str(authorization.approved_msr_id),
        "group": authorization.group,
        "requested_by_id": str(authorization.requested_by_id),
        "approved_by_id": str(authorization.approved_by_id),
        "approved_at": authorization.approved_at.isoformat(),
        "signer_name": authorization.signer_name,
        "signer_email": authorization.signer_email,
        "authority_basis": authorization.authority_basis,
        "evidence_reference": authorization.evidence_reference,
    }

    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    if not hmac.compare_digest(digest, authorization.digest):
        raise ValidationError("Customer-signer authorization integrity verification failed.")

    events = list(AuditEvent.objects.filter(
        entity_id=authorization.pk,
        action="CUSTOMER_SIGNER_AUTHORIZATION_APPROVED",
    )[:2])

    if len(events) != 1:
        raise ValidationError("Customer-signer approval audit evidence is missing or ambiguous.")

    expected_audit_payload = {**payload, "digest": digest}
    if events[0].payload != expected_audit_payload or events[0].actor_id != authorization.approved_by_id:
        raise ValidationError("Customer-signer approval audit evidence does not match.")

    return authorization
