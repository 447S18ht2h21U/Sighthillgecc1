"""Explicitly authorized, single-envelope fictional sandbox transmission.

Only the existing designated Completion Certificate may be sent.
No new envelopes, replacement documents, recipient changes, operational
signature authority, funding release or financial posting.
"""

import os

from base64 import b64decode
from hashlib import sha256
from urllib.request import Request, build_opener

import fitz

from django.db import connections, transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

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
    DESIGNATED_SANDBOX_RECIPIENT,
    single_evidence,
    validate_provider_draft,
    uuid_value,
)

from .completion_certificate_read_6069 import (
    ENVELOPE_ID,
    SIGNED_KIND,
    source_binding,
)

from .installation_inspection_transaction_6039 import (
    require_inspection_development_environment,
)


OPERATION = "SANDBOX_CERTIFICATE_SEND_6071"

FLAG = "GECC_CERTIFICATE_SANDBOX_SEND_ENABLED"

ATTEMPT_KIND = "CERT_SEND_ATTEMPT_6071"

RESULT_KIND = "CERT_SEND_RESULT_6071"


def authorize_context(actor, context):

    require_inspection_development_environment()

    if os.environ.get(FLAG) != "1":

        raise PermissionDenied(
            "Fictional certificate transmission is disabled."
        )

    if any(
        os.environ.get(name) == "1"
        for name in (
            "GECC_COMMERCIAL_SANDBOX_SEND_ENABLED",
            "GECC_SANDBOX_SIGNING_SEND_ENABLED",
            "GECC_CERTIFICATE_SANDBOX_DRAFT_ENABLED",
        )
    ):

        raise PermissionDenied(
            "Other sandbox transmission and draft creation "
            "operations must remain disabled."
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
        or context.get("recipient")
            != DESIGNATED_SANDBOX_RECIPIENT
        or context.get("fictional_send_confirmed") is not True
        or context.get("recipient_visual_review") is not True
        or context.get("operational_send_authorized") is not False
        or context.get("completion_authorized") is not False
    ):

        raise PermissionDenied(
            "Exact fictional transmission authorization required."
        )

    return current


def binding_for(actor):

    project, msr, binding, expected = source_binding(actor)

    context = {
        **binding,
        "operation": OPERATION,
        "read_only": False,
        "recipient": DESIGNATED_SANDBOX_RECIPIENT,
        "fictional_send_confirmed": True,
        "recipient_visual_review": True,
        "operational_send_authorized": False,
        "completion_authorized": False,
    }

    return project, msr, context, expected


def require_unused(project):

    if any(
        single_evidence(project, kind)
        for kind in (
            ATTEMPT_KIND,
            RESULT_KIND,
            SIGNED_KIND,
        )
    ):

        raise ValidationError(
            "A certificate transmission attempt already exists. "
            "Check its status. Do not send again."
        )


@transaction.atomic
def begin(
    *,
    actor,
    session_key,
    project_id,
    envelope_id,
    recipient,
    confirmed,
):

    if (
        str(project_id) != PROJECT_ID
        or envelope_id != ENVELOPE_ID
        or recipient != DESIGNATED_SANDBOX_RECIPIENT
        or confirmed is not True
    ):

        raise ValidationError(
            "Confirm the existing fictional envelope "
            "and its designated test recipient."
        )

    project, msr, context, expected = binding_for(actor)

    current = authorize_context(actor, context)

    require_unused(project)

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
        "envelope_id": ENVELOPE_ID,
        "recipient": DESIGNATED_SANDBOX_RECIPIENT,
        "fictional": True,
        "completion_authorized": False,
        "operational_send_authorized": False,
    }


@transaction.atomic
def verify_callback(actor, challenge, config):

    current = authorize_context(
        actor,
        challenge.context,
    )

    project, msr, context, expected = binding_for(current)

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
            "Certificate transmission authorization changed."
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

    require_unused(project)

    return project, msr, context, expected, proof


def document_check(expected, provider_bytes):

    original = b64decode(
        expected["documents"][0]["documentBase64"],
        validate=True,
    )

    if (
        type(provider_bytes) is not bytes
        or not provider_bytes.startswith(b"%PDF-")
        or not 0 < len(provider_bytes) <= 8 * 1024 * 1024
    ):

        raise ValidationError(
            "Provider draft PDF could not be verified."
        )

    original_hash = sha256(original).hexdigest()

    provider_hash = sha256(provider_bytes).hexdigest()

    with fitz.open(
        stream=original,
        filetype="pdf",
    ) as source:

        with fitz.open(
            stream=provider_bytes,
            filetype="pdf",
        ) as observed:

            if len(source) != 1 or len(observed) != 1:

                raise ValidationError(
                    "Unexpected Completion Certificate page count."
                )

            a = source[0]

            b = observed[0]

            if (
                a.rotation != b.rotation
                or a.rect != b.rect
                or " ".join(a.get_text().split())
                    != " ".join(b.get_text().split())
                or "FICTIONAL PREVIEW - NOT SIGNED OR AUTHORIZED"
                    not in b.get_text()
            ):

                raise ValidationError(
                    "Provider draft PDF content changed."
                )

    # PDF serialization may differ after provider processing.
    # Text and geometry comparison is not full visual equivalence.

    return {
        "original_pdf_sha256": original_hash,
        "provider_pdf_sha256": provider_hash,
        "byte_identical": original_hash == provider_hash,
        "text_and_page_geometry_match": True,
        "visual_layout_verified": False,
    }


@transaction.atomic
def reserve(
    *,
    actor,
    challenge,
    config,
    expected_context,
    document_evidence,
):

    project, msr, context, expected, proof = (
        verify_callback(actor, challenge, config)
    )

    if context != expected_context:

        raise ValidationError(
            "Certificate binding changed before transmission."
        )

    if (
        document_evidence["original_pdf_sha256"]
            != context["original_pdf_sha256"]
        or document_evidence["text_and_page_geometry_match"]
            is not True
        or document_evidence["visual_layout_verified"]
            is not False
    ):

        raise ValidationError(
            "Certificate document verification is incomplete."
        )

    data = {
        "binding": context,
        "state": "SEND_OUTCOME_UNKNOWN",
        "verification_id": str(proof.pk),
        "challenge_id": str(challenge.pk),
        "reserved_at": timezone.now().isoformat(),
        "reserved_by": str(actor.pk),
        "document_evidence": document_evidence,
        "fictional": True,
        "operational_send_authorized": False,
        "completion_authorized": False,
        "financial_posting_authorized": False,
    }

    reservation = ProjectEvidence.objects.create(
        msr=msr,
        kind=ATTEMPT_KIND,
        created_by=actor,
        data=data,
        digest=canonical_hash(data),
    )

    audit(
        actor,
        "installation.certificate_sandbox_send_started",
        project.pk,
        {
            "attempt_id": str(reservation.pk),
            "envelope_id": ENVELOPE_ID,
            "recipient": DESIGNATED_SANDBOX_RECIPIENT,
            "fictional": True,
        },
    )

    return reservation


@sensitive_variables()
def transmit_existing(account_id, token):

    require_inspection_development_environment()

    if (
        os.environ.get(FLAG) != "1"
        or docusign.BASE_URI
            != "https://demo.docusign.net"
        or docusign.configuration()["account_id"]
            != account_id
        or docusign.configuration()["blockers"]
    ):

        raise PermissionDenied(
            "Verified sandbox transmission configuration required."
        )

    account = uuid_value(account_id)

    envelope = uuid_value(ENVELOPE_ID)

    if (
        type(token) is not str
        or not 16 <= len(token) <= 16384
        or any(character.isspace() for character in token)
    ):

        raise PermissionDenied(
            "Transient sandbox OAuth token required."
        )

    url = (
        "https://demo.docusign.net"
        f"/restapi/v2.1/accounts/{account}"
        f"/envelopes/{envelope}"
    )

    request = Request(
        url,
        method="PUT",
        data=b'{"status":"sent"}',
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:

        with build_opener(
            docusign.NoRedirects()
        ).open(request, timeout=15) as response:

            if response.status not in (200, 201, 204):

                raise ValueError()

            if len(response.read(1048577)) > 1048576:

                raise ValueError()

    except Exception:

        raise ValidationError(
            "DocuSign transmission outcome requires review. "
            "Do not retry."
        ) from None


@transaction.atomic
def retain_result(
    *,
    actor,
    reservation,
    summary,
):

    original = ProjectEvidence.objects.get(
        pk=reservation.pk,
        kind=ATTEMPT_KIND,
    )

    from .models import Project

    project = Project.objects.select_for_update().get(
        pk=original.msr.project_id,
    )

    if (
        original.digest != canonical_hash(original.data)
        or original.created_by_id != actor.pk
        or original.data["state"] != "SEND_OUTCOME_UNKNOWN"
        or single_evidence(project, RESULT_KIND)
        or summary.get("envelopeId") != ENVELOPE_ID
        or summary.get("status") not in {
            "sent",
            "delivered",
            "signed",
            "completed",
        }
    ):

        raise ValidationError(
            "Provider transmission result requires reconciliation."
        )

    data = {
        "attempt_id": str(original.pk),
        "attempt_digest": original.digest,
        "binding": original.data["binding"],
        "state": "SANDBOX_SEND_OBSERVED",
        "provider_status": summary["status"],
        "observed_at": timezone.now().isoformat(),
        "fictional": True,
        "operational_send_authorized": False,
        "completion_authorized": False,
        "financial_posting_authorized": False,
    }

    result = ProjectEvidence.objects.create(
        msr=original.msr,
        kind=RESULT_KIND,
        created_by=actor,
        data=data,
        digest=canonical_hash(data),
    )

    audit(
        actor,
        "installation.certificate_sandbox_send_observed",
        project.pk,
        {
            "attempt_id": str(original.pk),
            "result_id": str(result.pk),
            "envelope_id": ENVELOPE_ID,
            "provider_status": summary["status"],
        },
    )

    return result


@sensitive_variables()
def finish(actor, challenge, config, token):

    if connections["default"].in_atomic_block:

        raise ValidationError(
            "Transmission requires a committed reservation."
        )

    project, msr, context, expected, proof = (
        verify_callback(actor, challenge, config)
    )

    account = context["account_id"]

    summary = sandbox.provider(
        account,
        ENVELOPE_ID,
        token,
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

    validate_provider_draft(
        expected,
        summary,
        recipients,
        documents,
        ENVELOPE_ID,
    )

    document_evidence = document_check(
        expected,
        signing_test.pdf_document(
            account,
            ENVELOPE_ID,
            "1",
            token,
        ),
    )

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
        )
    ):

        raise ValidationError(
            "Provider draft changed during verification."
        )

    if not summary.get("lastModifiedDateTime"):

        raise ValidationError(
            "Provider draft modification evidence unavailable."
        )

    reservation = reserve(
        actor=actor,
        challenge=challenge,
        config=config,
        expected_context=context,
        document_evidence=document_evidence,
    )

    # One durable reservation exists before the only PUT operation.
    # Never retry automatically after an ambiguous provider outcome.

    try:

        transmit_existing(
            account,
            token,
        )

        sent = sandbox.provider(
            account,
            ENVELOPE_ID,
            token,
        )

        result = retain_result(
            actor=actor,
            reservation=reservation,
            summary=sent,
        )

    except Exception:

        raise ValidationError(
            "Existing certificate transmission requires reconciliation. "
            "Do not send again or create another envelope."
        ) from None

    return {
        "status": "SANDBOX_CERTIFICATE_SEND_OBSERVED",
        "envelope_id": ENVELOPE_ID,
        "recipient": DESIGNATED_SANDBOX_RECIPIENT,
        "provider_status": sent["status"],
        "attempt_id": str(reservation.pk),
        "result_id": str(result.pk),
        "fictional": True,
        "tokens_retained": False,
        "operational_send_authorized": False,
        "completion_authorized": False,
        "message": (
            "Fictional sandbox transmission observed. "
            "Check the designated recipient email. "
            "Do not sign if the document or fields are incorrect."
        ),
    }


@transaction.atomic
def status(actor):

    project, msr, context, expected = binding_for(actor)

    attempt = single_evidence(
        project,
        ATTEMPT_KIND,
    )

    result = single_evidence(
        project,
        RESULT_KIND,
    )

    state = "NOT_SENT"

    provider_status = None

    if attempt is not None:

        if (
            attempt.msr_id != msr.pk
            or attempt.digest != canonical_hash(attempt.data)
            or attempt.data.get("binding") != context
            or attempt.data.get("state") != "SEND_OUTCOME_UNKNOWN"
            or attempt.data.get("reserved_by")
                != str(attempt.created_by_id)
            or attempt.data.get("fictional") is not True
            or attempt.data.get("completion_authorized") is not False
        ):

            raise ValidationError(
                "Transmission attempt integrity requires review."
            )

        state = "RECONCILIATION_REQUIRED"

        if result is not None:

            if (
                result.msr_id != msr.pk
                or result.digest != canonical_hash(result.data)
                or result.data.get("binding") != context
                or result.data.get("attempt_id") != str(attempt.pk)
                or result.data.get("attempt_digest") != attempt.digest
                or result.created_by_id != attempt.created_by_id
                or result.data.get("state") != "SANDBOX_SEND_OBSERVED"
                or result.data.get("provider_status") not in {
                    "sent", "delivered", "signed", "completed"
                }
            ):

                raise ValidationError(
                    "Transmission result integrity requires review."
                )

            state = "SEND_OBSERVED"

            provider_status = result.data["provider_status"]

    elif result is not None:

        raise ValidationError(
            "Orphaned transmission result."
        )

    config = docusign.configuration()

    blockers = list(config["blockers"])

    if config["account_id"] != context["account_id"]:

        blockers.append(
            "Configured sandbox account does not match."
        )

    try:

        authorize_context(actor, context)

    except PermissionDenied:

        blockers.append(
            "Controlled sandbox transmission is disabled."
        )

    if single_evidence(project, SIGNED_KIND):

        blockers.append(
            "Completed sandbox evidence already exists."
        )

    return {
        "project_id": PROJECT_ID,
        "package_id": PACKAGE_ID,
        "package_digest": PACKAGE_DIGEST,
        "envelope_id": ENVELOPE_ID,
        "recipient": DESIGNATED_SANDBOX_RECIPIENT,
        "state": state,
        "provider_status": provider_status,
        "send_available": state == "NOT_SENT" and not blockers,
        "blockers": blockers,
        "fictional": True,
        "automatic_retry_allowed": False,
        "operational_send_authorized": False,
        "completion_authorized": False,
    }
