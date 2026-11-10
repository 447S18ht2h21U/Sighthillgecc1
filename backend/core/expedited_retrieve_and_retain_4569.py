
'''Sandbox-only provider retrieval and atomic unverified document retention.

Provider-origin and approval claims intentionally remain false.
There is no envelope creation, sending, or installation authorization.
'''
from hashlib import sha256

from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import signing_test
from .documents import canonical_hash
from .models import ExpeditedEnvelopeBinding, Role
from .expedited_sandbox_read_4568 import (
    read_unified_sandbox_candidate,
    STABILITY_FIELDS,
)
from .expedited_observation_storage_4569 import (
    retain_unverified_expedited_observation,
    _uuid,
)


def retrieve_and_retain_expedited_sandbox_candidate(
    *, actor, binding_id, token, offline_envelope,
):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Sandbox integration is not live-enabled.")

    if (
        actor is None
        or getattr(actor, "is_active", False) is not True
        or getattr(actor, "role", None)
            not in (Role.CEO, Role.SALES_MANAGER)
        or not getattr(actor, "pk", None)
    ):
        raise PermissionDenied("Authorized initiator required.")

    binding_id = _uuid(binding_id)
    binding = (
        ExpeditedEnvelopeBinding.objects
        .select_related("attempt__msr__project")
        .get(pk=binding_id)
    )
    attempt = binding.attempt
    msr = attempt.msr

    if (
        attempt.initiated_by_id != actor.pk
        or binding.bound_by_id != actor.pk
        or msr.status != "APPROVED"
        or msr.project.current_approved_id != msr.pk
        or canonical_hash(msr.snapshot) != attempt.snapshot_sha256
    ):
        raise ValidationError("Approved MSR attempt binding differs.")

    if type(offline_envelope) is not dict:
        raise ValidationError("Protected offline envelope required.")
    if offline_envelope.get("source_msr_id") != str(msr.pk):
        raise ValidationError("Offline source MSR differs.")

    signers = offline_envelope.get("recipients")
    signers = signers.get("signers") if type(signers) is dict else None
    if type(signers) is not list or len(signers) != 3:
        raise ValidationError("Three protected signers required.")

    if type(attempt.recipient_manifest) is not list:
        raise ValidationError("Recorded recipient manifest malformed.")

    for number, (observed, recorded) in enumerate(
        zip(signers, attempt.recipient_manifest), 1
    ):
        if type(observed) is not dict or type(recorded) is not dict:
            raise ValidationError("Recipient identity malformed.")
        if (
            observed.get("recipientId") != str(number)
            or str(observed.get("routingOrder")) != str(number)
            or observed.get("name") != recorded.get("name")
            or observed.get("email", "").casefold()
                != recorded.get("email")
        ):
            raise ValidationError("Recipient identity changed.")

    docs = offline_envelope.get("documents")
    if type(docs) is not list or len(docs) != 2:
        raise ValidationError("Two protected source PDFs required.")

    doc_hashes = {}
    for number, item in enumerate(docs, 1):
        if (
            type(item) is not dict
            or item.get("documentId") != str(number)
            or type(item.get("documentBase64")) is not str
        ):
            raise ValidationError("Source document identity changed.")
        doc_hashes[str(number)] = canonical_hash(
            item["documentBase64"]
        )

    expected_source = canonical_hash({
        "msr_id": str(msr.pk),
        "snapshot_sha256": attempt.snapshot_sha256,
        "proposed_date": attempt.proposed_date.isoformat(),
        "recipients": attempt.recipient_manifest,
        "document_hashes": doc_hashes,
    })
    if expected_source != attempt.source_digest:
        raise ValidationError("Immutable signing source fingerprint differs.")

    account = str(binding.provider_account_id)
    envelope = str(binding.provider_envelope_id)

    # Existing reader checks configured sandbox, completed state,
    # recipient/tab evidence, document listing, PDF structure and
    # envelope stability. It returns hashes but never PDF bytes.
    candidate = read_unified_sandbox_candidate(
        account_id=account,
        envelope_id=envelope,
        token=token,
        offline_envelope=offline_envelope,
    )

    if (
        type(candidate) is not dict
        or candidate.get("envelope_id") != envelope
        or candidate.get("source_msr_id") != str(msr.pk)
        or candidate.get("status")
            != "SANDBOX_READ_STRUCTURAL_CANDIDATE_ONLY"
        or candidate.get("installation_authorized") is not False
        or candidate.get("provider_authenticated") is not False
    ):
        raise ValidationError("Guarded provider candidate differs.")

    expected = candidate.get("document_hashes")
    if type(expected) is not dict or set(expected) != {
        "1", "2", "certificate"
    }:
        raise ValidationError("Three provider document hashes required.")

    # Download again through the same restricted read-only provider
    # adapter; require exact matches to the protected reader's hashes.
    pdfs = {}
    for document_id in ("1", "2", "certificate"):
        content = signing_test.pdf_document(
            account, envelope, document_id, token
        )
        if (
            type(content) is not bytes
            or sha256(content).hexdigest() != expected[document_id]
        ):
            raise ValidationError("Provider document changed after validation.")
        pdfs[document_id] = content

    # Reconfirm the identical envelope state after all PDF downloads.
    stability = candidate.get("envelope_stability")
    if (
        type(stability) is not dict
        or set(stability) != set(STABILITY_FIELDS)
        or stability.get("envelopeId") != envelope
        or stability.get("status") != "completed"
        or not stability.get("lastModifiedDateTime")
        or not stability.get("completedDateTime")
    ):
        raise ValidationError("Verified envelope stability evidence required.")

    final_summary = signing_test.provider(account, envelope, token)
    if (
        type(final_summary) is not dict
        or any(
            final_summary.get(field) != stability[field]
            for field in STABILITY_FIELDS
        )
    ):
        raise ValidationError("DocuSign envelope changed during PDF retention.")

    result = retain_unverified_expedited_observation(
        actor=actor,
        binding_id=binding_id,
        candidate=candidate,
        pdf_bytes=pdfs,
    )
    if (
        result.get("installation_authorized") is not False
        or result.get("provider_authenticated") is not False
        or result.get("send_authorized") is not False
    ):
        raise ValidationError("Retained observation claimed authority.")

    return result
