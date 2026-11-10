"""Read-only trusted recipient binding for unified expedited documents.

Administrative approval is not authenticated document signing.
No DocuSign payload, customer send, or installation permission is created.
"""
from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import ProjectEvidence, Role, User
from .expedited_signing_preflight_4567 import (
    assess_unified_signing_preflight,
)
from .expedited_signer_identity_4567 import (
    assess_expedited_customer_identity,
)
from .expedited_service_review_4565 import REVIEW_KIND
from .expedited_manager_decision_4565 import DECISION_KIND


def assess_unified_recipients(*, actor, project_id):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Expedited recipient routing is not live-enabled.")

    bound = assess_unified_signing_preflight(
        actor=actor, project_id=project_id,
    )
    customer = assess_expedited_customer_identity(
        actor=actor, project_id=project_id,
    )

    common = (
        "project_id", "msr_id", "msr_version",
        "snapshot_sha256", "proposed_date",
    )
    if (
        type(bound) is not dict or type(customer) is not dict
        or any(bound.get(k) != customer.get(k) for k in common)
        or bound.get("administrative_chain_reviewed") is not True
        or bound.get("send_authorized") is not False
        or bound.get("installation_authorized") is not False
        or customer.get("expedited_signer_authorized") is not False
        or customer.get("send_authorized") is not False
        or customer.get("installation_authorized") is not False
    ):
        raise ValidationError("Protected recipient identity bindings differ.")

    references = bound.get("administrative_records")
    if type(references) is not dict:
        raise ValidationError("Administrative evidence references are missing.")

    roles = (
        ("INSTALLATION_MANAGER", DECISION_KIND,
         "manager_decision_id", "manager_decision_digest",
         Role.INSTALLATION_MANAGER),
        ("COMPTROLLER", REVIEW_KIND,
         "review_id", "review_digest", Role.COMPTROLLER),
    )

    recipients = [{
        "recipient_id": "1",
        "routing_order": 1,
        "role": "CUSTOMER",
        "name": customer.get("customer_signer_name"),
        "email": customer.get("customer_signer_email"),
        "customer_authorization_reference":
            customer.get("commercial_signer_authorization_id"),
    }]

    for order, (name, kind, pk_field, digest_field, required_role) in (
        enumerate(roles, start=2)
    ):
        record_id = references.get(pk_field)
        expected_digest = references.get(digest_field)
        if (
            type(record_id) is not str or not record_id
            or type(expected_digest) is not str
            or len(expected_digest) != 64
        ):
            raise ValidationError("Reviewer approval reference is incomplete.")

        evidence = ProjectEvidence.objects.filter(
            pk=record_id, kind=kind,
            msr_id=bound["msr_id"],
        ).first()
        if (
            evidence is None
            or evidence.digest != expected_digest
            or type(evidence.data) is not dict
            or evidence.data.get("msr_id") != bound["msr_id"]
            or evidence.data.get("proposed_date") != bound["proposed_date"]
        ):
            raise ValidationError("Reviewer evidence changed or no longer matches.")

        reviewer = User.objects.filter(pk=evidence.created_by_id).first()
        if (
            reviewer is None
            or reviewer.is_active is not True
            or reviewer.role != required_role
            or type(reviewer.email) is not str
            or not reviewer.email.strip()
        ):
            raise PermissionDenied("Required reviewer is no longer authorized.")

        full_name = reviewer.get_full_name().strip()
        if not full_name:
            raise ValidationError("Reviewer must have a full name.")

        recipients.append({
            "recipient_id": str(order),
            "routing_order": order,
            "role": name,
            "user_id": str(reviewer.pk),
            "name": full_name,
            "email": reviewer.email.strip(),
            "evidence_id": str(evidence.pk),
            "evidence_digest": evidence.digest,
        })

    emails = [str(item.get("email", "")).casefold() for item in recipients]
    if (
        any(not str(item.get("name", "")).strip() for item in recipients)
        or any("@" not in email or any(ch.isspace() for ch in email)
               for email in emails)
        or len(set(emails)) != 3
        or recipients[1]["user_id"] == recipients[2]["user_id"]
    ):
        raise ValidationError("Three distinct signing identities are required.")

    return {
        "status": "THREE_RECIPIENT_IDENTITIES_BOUND_NO_SIGNING_AUTHORITY",
        **{key: bound[key] for key in common},
        "envelope_count": 1,
        "documents": ["CUSTOMER_SOW", "EXPEDITED_SERVICE"],
        "recipients": recipients,
        "administrative_chain_reviewed": True,
        "expedited_signer_authorized": False,
        "provider_signatures_verified": False,
        "send_authorized": False,
        "installation_authorized": False,
    }
