"""Read-only fictional Completion Certificate provider retrieval.

No envelope creation, transmission, payment or operational completion.
Provider metadata and retrieved PDFs remain sandbox evidence only.
"""

import os

from base64 import b64encode, b64decode
from hashlib import sha256
from io import BytesIO

from django.db import connections, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.debug import sensitive_variables

from pypdf import PdfReader

from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from . import docusign, sandbox, signing_test

from .documents import canonical_hash

from .models import (
    DocusignChallenge,
    DocusignVerification,
    ProjectEvidence,
    Role,
    User,
)

from .services import audit

from .completion_certificate_provider_6063 import (
    PROJECT_ID,
    PACKAGE_ID,
    PACKAGE_DIGEST,
    RESERVATION_KIND,
    RESULT_KIND,
    OBSERVATION_KIND,
    current_package,
    single_evidence,
    uuid_value,
    validate_provider_draft,
)

from .installation_inspection_transaction_6039 import (
    require_inspection_development_environment,
)


OPERATION = "SANDBOX_CERTIFICATE_READ_6069"

FLAG = "GECC_CERTIFICATE_SANDBOX_READ_ENABLED"

SIGNED_KIND = "CERT_SIGNED_SANDBOX_6069"

ENVELOPE_ID = "451126d1-b943-889f-81df-12b98cb11a4a"

MAX_PDF_BYTES = 8 * 1024 * 1024


def authorize_context(actor, context):

    require_inspection_development_environment()

    if os.environ.get(FLAG) != "1":

        raise PermissionDenied(
            "Certificate sandbox retrieval is disabled."
        )

    if (
        not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None)
            != Role.INSTALLATION_MANAGER
    ):

        raise PermissionDenied(
            "Assigned Installation Manager required."
        )

    current = User.objects.filter(
        pk=actor.pk,
        is_active=True,
        role=Role.INSTALLATION_MANAGER,
    ).first()

    if current is None:

        raise PermissionDenied(
            "Current Installation Manager required."
        )

    if (
        type(context) is not dict
        or context.get("operation") != OPERATION
        or context.get("project_id") != PROJECT_ID
        or context.get("package_id") != PACKAGE_ID
        or context.get("package_digest") != PACKAGE_DIGEST
        or context.get("envelope_id") != ENVELOPE_ID
        or context.get("read_only") is not True
        or context.get("send_authorized") is not False
    ):

        raise PermissionDenied(
            "Exact read-only fictional envelope required."
        )

    return current


def checked(record, msr):

    if (
        record is None
        or record.msr_id != msr.pk
        or type(record.data) is not dict
        or canonical_hash(record.data) != record.digest
        or record.data.get("package_digest") != PACKAGE_DIGEST
        or record.data.get("send_authorized") is not False
        or record.data.get("signed") is not False
        or record.data.get("completion_authorized") is not False
    ):

        raise ValidationError(
            "Existing draft tracking evidence requires review."
        )

    return record.data


def source_binding(actor):

    project, msr, package, certificate, payload = (
        current_package(actor)
    )

    reservation = single_evidence(
        project,
        RESERVATION_KIND,
    )

    result = single_evidence(
        project,
        RESULT_KIND,
    )

    observation = single_evidence(
        project,
        OBSERVATION_KIND,
    )

    r = checked(reservation, msr)

    d = checked(result, msr)

    o = checked(observation, msr)

    if (
        r.get("state") != "PROVIDER_OUTCOME_UNKNOWN"
        or r.get("project_id") != PROJECT_ID
        or r.get("msr_id") != str(msr.pk)
        or r.get("package_id") != PACKAGE_ID
        or r.get("certificate_id") != str(certificate.pk)
        or r.get("certificate_digest") != certificate.digest
        or r.get("payload_digest") != canonical_hash(payload)
        or r.get("reserved_by") != str(reservation.created_by_id)
        or d.get("reservation_id") != str(reservation.pk)
        or d.get("reservation_digest") != reservation.digest
        or d.get("envelope_id") != ENVELOPE_ID
        or d.get("provider_status") != "created"
        or d.get("state") != "CREATED_UNVALIDATED"
        or d.get("account_id") != r.get("account_id")
        or result.created_by_id != reservation.created_by_id
        or o.get("result_id") != str(result.pk)
        or o.get("result_digest") != result.digest
        or o.get("envelope_id") != ENVELOPE_ID
        or o.get("account_id") != d.get("account_id")
        or o.get("state") != "DRAFT_METADATA_VALIDATED"
        or observation.created_by_id != result.created_by_id
        or o.get("checks") != {
            "recipient_metadata_verified": True,
            "tab_metadata_verified": True,
            "document_inventory_verified": True,
            "provider_pdf_content_verified": False,
            "visual_layout_verified": False,
        }
    ):

        raise ValidationError(
            "Permanent provider envelope binding is invalid."
        )

    account = uuid_value(d["account_id"])

    context = {
        "operation": OPERATION,
        "project_id": PROJECT_ID,
        "msr_id": str(msr.pk),
        "package_id": PACKAGE_ID,
        "package_digest": PACKAGE_DIGEST,
        "certificate_id": str(certificate.pk),
        "certificate_digest": certificate.digest,
        "original_pdf_sha256": certificate.data["pdf_sha256"],
        "reservation_id": str(reservation.pk),
        "reservation_digest": reservation.digest,
        "result_id": str(result.pk),
        "result_digest": result.digest,
        "observation_id": str(observation.pk),
        "observation_digest": observation.digest,
        "account_id": account,
        "envelope_id": ENVELOPE_ID,
        "read_only": True,
        "send_authorized": False,
    }

    return project, msr, context, payload


@transaction.atomic
def begin(*, actor, session_key, project_id, confirmed):

    if (
        str(project_id) != PROJECT_ID
        or confirmed is not True
    ):

        raise ValidationError(
            "Confirm read-only fictional certificate retrieval."
        )

    project, msr, context, payload = source_binding(actor)

    current = authorize_context(actor, context)

    config = docusign.configuration()

    if (
        config["blockers"]
        or config["account_id"] != context["account_id"]
    ):

        raise ValidationError(
            "Configured sandbox account does not match."
        )

    result = docusign.begin(
        current,
        session_key,
        context,
    )

    return {
        **result,
        "operation": OPERATION,
        "read_only": True,
        "send_authorized": False,
        "completion_authorized": False,
    }


@transaction.atomic
def verify_callback(actor, challenge, config):

    current = authorize_context(
        actor,
        challenge.context,
    )

    project, msr, context, payload = source_binding(current)

    stored = (
        DocusignChallenge.objects.select_for_update()
        .get(pk=challenge.pk)
    )

    fresh = docusign.configuration()

    if (
        stored.actor_id != current.pk
        or stored.consumed_at is None
        or stored.expires_at <= timezone.now()
        or stored.context != context
        or challenge.context != context
        or fresh["blockers"]
        or fresh["account_id"] != context["account_id"]
        or config["account_id"] != context["account_id"]
        or stored.configuration_digest
            != docusign.configuration_digest(fresh)
    ):

        raise PermissionDenied(
            "Certificate retrieval authorization changed."
        )

    proof = DocusignVerification.objects.filter(
        actor=current,
        challenge=stored,
    ).first()

    if (
        proof is None
        or canonical_hash(proof.identity) != proof.digest
        or proof.identity.get("purpose") != OPERATION
        or proof.identity.get("environment") != "SANDBOX"
        or proof.identity.get("account_id")
            != context["account_id"]
        or proof.identity.get("base_uri")
            != "https://demo.docusign.net"
        or proof.identity.get("tokens_retained") is not False
    ):

        raise PermissionDenied(
            "Authenticated sandbox account evidence required."
        )

    return context, payload, proof


def verified_timestamp(value):

    try:

        parsed = parse_datetime(value)

    except (ValueError, TypeError):

        parsed = None

    if (
        parsed is None
        or timezone.is_naive(parsed)
        or parsed > timezone.now()
    ):

        raise ValidationError(
            "Provider signing timestamp is invalid."
        )

    return parsed


def completed_metadata(
    expected,
    summary,
    recipients,
    documents,
):

    if (
        summary.get("envelopeId") != ENVELOPE_ID
        or summary.get("status") != "completed"
    ):

        raise ValidationError(
            "Completed provider envelope required."
        )

    # Reuse the established recipient, document and tab checks.
    # Only the lifecycle status differs from the draft review.

    validate_provider_draft(
        expected,
        {**summary, "status": "created"},
        recipients,
        documents,
        ENVELOPE_ID,
    )

    signer = recipients["signers"][0]

    if signer.get("status") != "completed":

        raise ValidationError(
            "The designated customer has not completed signing."
        )

    signed_at = verified_timestamp(
        signer.get("signedDateTime")
    )

    completed_at = verified_timestamp(
        summary.get("completedDateTime")
    )

    if signed_at > completed_at:

        raise ValidationError(
            "Provider completion timestamps are inconsistent."
        )

    return {
        "signed_at": signed_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "provider_status": "completed",
        "recipient_metadata_verified": True,
        "tab_metadata_verified": True,
        "document_inventory_verified": True,
    }


def pdf_entry(document_id, content):

    if (
        type(content) is not bytes
        or not content.startswith(b"%PDF-")
        or not 0 < len(content) <= MAX_PDF_BYTES
    ):

        raise ValidationError(
            "Invalid retained provider PDF."
        )

    reader = PdfReader(BytesIO(content))

    if reader.is_encrypted:

        raise ValidationError(
            "Unexpected encrypted provider PDF."
        )

    pages = len(reader.pages)

    if (
        document_id == "1"
        and pages != 1
    ) or (
        document_id == "certificate"
        and not 1 <= pages <= 150
    ):

        raise ValidationError(
            "Unexpected provider PDF page count."
        )

    return {
        "document_id": document_id,
        "kind": (
            "SIGNED_COMPLETION_CERTIFICATE"
            if document_id == "1"
            else "DOCUSIGN_CERTIFICATE_OF_COMPLETION"
        ),
        "pdf_sha256": sha256(content).hexdigest(),
        "size_bytes": len(content),
        "pages": pages,
        "pdf_base64": b64encode(content).decode("ascii"),
    }


def validate_retained(record, context):

    data = record.data

    if (
        canonical_hash(data) != record.digest
        or data.get("binding") != context
        or data.get("status")
            != "SANDBOX_COMPLETED_EVIDENCE_RETAINED"
        or data.get("fictional") is not True
        or data.get("provider_authenticated") is not True
        or data.get("send_authorized") is not False
        or data.get("financial_posting_authorized") is not False
        or data.get("completion_authorized") is not False
        or data.get("operational_signature_verified") is not False
    ):

        raise ValidationError(
            "Retained sandbox evidence integrity failed."
        )

    entries = data.get("documents")

    if (
        type(entries) is not list
        or len(entries) != 2
        or {row["document_id"] for row in entries}
            != {"1", "certificate"}
    ):

        raise ValidationError(
            "Retained provider PDF bundle is incomplete."
        )

    for row in entries:

        content = b64decode(
            row["pdf_base64"],
            validate=True,
        )

        if pdf_entry(row["document_id"], content) != row:

            raise ValidationError(
                "Retained provider PDF integrity failed."
            )

    return data


@transaction.atomic
def retain(
    *,
    actor,
    challenge,
    config,
    context,
    metadata,
    entries,
):

    verified, payload, proof = verify_callback(
        actor,
        challenge,
        config,
    )

    if verified != context:

        raise ValidationError(
            "Certificate changed during provider retrieval."
        )

    project, msr, fresh_context, payload = (
        source_binding(actor)
    )

    existing = single_evidence(
        project,
        SIGNED_KIND,
    )

    if existing:

        validate_retained(existing, context)

        return existing, False

    data = {
        "binding": context,
        "status": "SANDBOX_COMPLETED_EVIDENCE_RETAINED",
        "fictional": True,
        "provider_authenticated": True,
        "provider_metadata": metadata,
        "verification_id": str(proof.pk),
        "challenge_id": str(challenge.pk),
        "retained_by": str(actor.pk),
        "retained_at": timezone.now().isoformat(),
        "documents": entries,
        "tokens_retained": False,
        "send_authorized": False,
        "visual_layout_verified": False,
        "original_pdf_content_equivalence_verified": False,
        "operational_signature_verified": False,
        "financial_posting_authorized": False,
        "receipt_authorized": False,
        "completion_authorized": False,
    }

    record = ProjectEvidence.objects.create(
        msr=msr,
        kind=SIGNED_KIND,
        created_by=actor,
        data=data,
        digest=canonical_hash(data),
    )

    validate_retained(record, context)

    audit(
        actor,
        "installation.certificate_sandbox_evidence_retained",
        project.pk,
        {
            "record_id": str(record.pk),
            "envelope_id": ENVELOPE_ID,
            "document_hashes": [
                row["pdf_sha256"]
                for row in entries
            ],
            "fictional": True,
            "completion_authorized": False,
        },
    )

    return record, True


@sensitive_variables()
def finish(actor, challenge, config, token):

    if connections["default"].in_atomic_block:

        raise ValidationError(
            "Provider retrieval requires an independent transaction."
        )

    if (
        type(token) is not str
        or not 16 <= len(token) <= 16384
        or any(character.isspace() for character in token)
    ):

        raise PermissionDenied(
            "Transient authenticated OAuth token required."
        )

    context, expected, proof = verify_callback(
        actor,
        challenge,
        config,
    )

    account = context["account_id"]

    # These are exclusively read operations.
    # No payload is supplied to the provider transport.

    summary = sandbox.provider(
        account,
        ENVELOPE_ID,
        token,
    )

    if summary.get("envelopeId") != ENVELOPE_ID:

        raise ValidationError(
            "Provider returned a different envelope."
        )

    status = summary.get("status")

    if status in {
        "created",
        "sent",
        "delivered",
        "signed",
        "declined",
        "voided",
    }:

        return {
            "status": "SANDBOX_CERTIFICATE_NOT_COMPLETED",
            "provider_status": status,
            "envelope_id": ENVELOPE_ID,
            "signed_documents_retained": False,
            "send_authorized": False,
            "completion_authorized": False,
            "read_only": True,
        }

    if status != "completed":

        raise ValidationError(
            "Unexpected provider envelope lifecycle status."
        )

    recipients = sandbox.provider(
        account,
        ENVELOPE_ID,
        token,
        resource="/recipients?include_tabs=true",
    )

    documents = sandbox.provider(
        account,
        ENVELOPE_ID,
        token,
        resource="/documents",
    )

    metadata = completed_metadata(
        expected,
        summary,
        recipients,
        documents,
    )

    entries = [
        pdf_entry(
            document_id,
            signing_test.pdf_document(
                account,
                ENVELOPE_ID,
                document_id,
                token,
            ),
        )
        for document_id in ("1", "certificate")
    ]

    after = sandbox.provider(
        account,
        ENVELOPE_ID,
        token,
    )

    if any(
        after.get(key) != summary.get(key)
        for key in (
            "envelopeId",
            "status",
            "lastModifiedDateTime",
            "completedDateTime",
        )
    ):

        raise ValidationError(
            "Envelope changed during retrieval."
        )

    record, created = retain(
        actor=actor,
        challenge=challenge,
        config=config,
        context=context,
        metadata=metadata,
        entries=entries,
    )

    return {
        "status": "SANDBOX_COMPLETED_EVIDENCE_RETAINED",
        "envelope_id": ENVELOPE_ID,
        "record_id": str(record.pk),
        "created": created,
        "signed_documents_retained": True,
        "provider_authenticated": True,
        "read_only": True,
        "send_authorized": False,
        "operational_signature_verified": False,
        "completion_authorized": False,
        "tokens_retained": False,
    }
