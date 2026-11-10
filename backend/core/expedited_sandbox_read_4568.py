
'''Development-only unified envelope read and structural reconciliation.

This is an unregistered internal service. OAuth callback integration,
authorization of the envelope origin, provider-signature semantics,
durable storage and distribution are NOT implemented here.
'''
from uuid import UUID

from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import docusign, signing_test
from .expedited_tab_contract_4568 import validate_offline_tab_contract
from .expedited_retention_evidence_4568 import validate_retention_candidate

STABILITY_FIELDS = (
    "envelopeId", "status",
    "lastModifiedDateTime", "completedDateTime",
)


def read_unified_sandbox_candidate(
    *, account_id, envelope_id, token, offline_envelope,
):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Unified sandbox retrieval is not live-enabled.")

    try:
        account = str(UUID(account_id))
        envelope = str(UUID(envelope_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Valid DocuSign identifiers required.") from None

    if account != account_id or envelope != envelope_id:
        raise ValidationError("Canonical DocuSign identifiers required.")

    config = docusign.configuration()
    if (
        type(config) is not dict
        or config.get("blockers")
        or config.get("account_id") != account
    ):
        raise PermissionDenied("Configured sandbox account is unavailable.")

    if type(token) is not str or not 1 <= len(token) <= 16384:
        raise ValidationError("Authenticated short-lived provider token required.")

    if type(offline_envelope) is not dict:
        raise ValidationError("Protected offline envelope required.")

    checked = validate_offline_tab_contract(offline_envelope)
    if (
        type(checked) is not dict
        or checked.get("status") != "OFFLINE_TAB_CONTRACT_VALIDATED"
        or checked.get("provider_behavior_verified") is not False
        or checked.get("send_authorized") is not False
        or checked.get("installation_authorized") is not False
    ):
        raise ValidationError("Offline signing contract failed.")

    # Existing adapter enforces the sandbox provider host, bounded
    # response sizes, no redirects, and read-only resource paths.
    before = signing_test.provider(account, envelope, token)
    if (
        type(before) is not dict
        or before.get("envelopeId") != envelope
        or before.get("status") != "completed"
        or not before.get("lastModifiedDateTime")
        or not before.get("completedDateTime")
    ):
        raise ValidationError("Completed envelope observation required.")

    recipients = signing_test.provider(
        account, envelope, token, resource="/recipients?include_tabs=true"
    )
    documents = signing_test.provider(
        account, envelope, token, resource="/documents"
    )
    pdfs = {
        doc_id: signing_test.pdf_document(
            account, envelope, doc_id, token
        )
        for doc_id in ("1", "2", "certificate")
    }

    result = validate_retention_candidate(
        expected_envelope_id=envelope,
        offline_envelope=offline_envelope,
        summary=before,
        recipients=recipients,
        documents=documents,
        signed_pdfs=pdfs,
    )

    # Detect modifications or a changed completion state across reads.
    after = signing_test.provider(account, envelope, token)
    if (
        type(after) is not dict
        or any(before.get(k) != after.get(k) for k in STABILITY_FIELDS)
    ):
        raise ValidationError(
            "DocuSign envelope changed during retrieval; recheck required."
        )

    if (
        type(result) is not dict
        or result.get("status")
            != "THREE_DOCUMENT_STRUCTURAL_CANDIDATE_ONLY"
        or result.get("envelope_id") != envelope
        or set(result.get("retrieved_document_hashes", {}))
            != {"1", "2", "certificate"}
        or result.get("provider_authenticated") is not False
        or result.get("installation_authorized") is not False
    ):
        raise ValidationError("Structural retention response failed closed.")

    # Deliberately return only hashes/metadata, never token or PDF bytes.
    # The read's authenticated OAuth origin is not yet tied to a durable
    # MSR-specific signing attempt, so authority flags stay false.
    return {
        "status": "SANDBOX_READ_STRUCTURAL_CANDIDATE_ONLY",
        "envelope_id": envelope,
        "source_msr_id": result["source_msr_id"],
        "document_hashes": dict(result["retrieved_document_hashes"]),
        "envelope_stability": {k: after[k] for k in STABILITY_FIELDS},
        "manager_candidate_decision":
            result["manager_candidate_decision"],
        "comptroller_candidate_decision":
            result["comptroller_candidate_decision"],
        "provider_origin_bound_to_msr": False,
        "provider_authenticated": False,
        "signatures_verified": False,
        "durably_retained": False,
        "distribution_verified": False,
        "expedited_authorized": False,
        "installation_authorized": False,
        "send_authorized": False,
    }
