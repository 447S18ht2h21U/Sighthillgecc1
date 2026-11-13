"""Immutable, audited sandbox completion evidence retention.

Not a project-completion gate. Requires separately enabled OAuth callback,
current release binding, verified provider response, and retained PDF bytes.
"""
import hashlib
import os
from uuid import UUID

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .models import (
    CompletionEnvelopeAttempt,
    CompletionSignatureVerification,
    CompletionSignatureDocument,
    Project,
    Role,
)
from .services import audit


def validated_pdf_bundle(evidence):
    """Validate exact provider manifest/byte correspondence without DB access."""
    if not isinstance(evidence, dict):
        raise ValidationError("Provider evidence is missing.")

    if (
        evidence.get("provider_response_validated") is not True
        or evidence.get("completion_authorized") is not False
        or evidence.get("project_completed") is not False
    ):
        raise ValidationError("Untrusted completion evidence.")

    manifest = evidence.get("pdf_manifest")
    pdfs = evidence.get("_validated_pdf_bytes")

    if not isinstance(manifest, list) or not isinstance(pdfs, dict):
        raise ValidationError("Provider PDF bundle is incomplete.")

    if not 2 <= len(manifest) <= 9:
        raise ValidationError("Invalid completed-envelope document count.")

    ids = []
    matched = []
    total = 0

    for item in manifest:
        if not isinstance(item, dict):
            raise ValidationError("Malformed PDF manifest.")

        document_id = item.get("document_id")
        digest = item.get("pdf_sha256")
        size = item.get("size_bytes")

        if (
            not isinstance(document_id, str)
            or not document_id
            or len(document_id) > 20
            or document_id in ids
            or not (
                document_id == "certificate"
                or (
                    document_id.isascii()
                    and document_id.isdecimal()
                    and int(document_id) > 0
                )
            )
            or not isinstance(digest, str)
            or len(digest) != 64
            or not isinstance(size, int)
            or isinstance(size, bool)
        ):
            raise ValidationError("Invalid provider PDF identity.")

        content = pdfs.get(document_id)
        if not isinstance(content, bytes):
            raise ValidationError("Retained PDF bytes are missing.")

        total += len(content)

        if (
            len(content) != size
            or size < 8
            or size > 8 * 1024 * 1024
            or total > 24 * 1024 * 1024
            or not content.startswith(b"%PDF-")
            or hashlib.sha256(content).hexdigest() != digest
        ):
            raise ValidationError("Retained PDF fingerprint mismatch.")

        ids.append(document_id)
        matched.append((document_id, digest, content))

    if set(ids) != set(pdfs) or ids.count("certificate") != 1:
        raise ValidationError("DocuSign audit certificate is missing.")

    if any(
        key in evidence for key in ("access_token", "refresh_token", "code")
    ):
        raise ValidationError("Provider credentials cannot be retained.")

    return tuple(matched)


@transaction.atomic
def retain_authenticated_completion(*, actor, attempt_id, challenge, evidence):
    """Store one immutable verification and its PDFs atomically.

    No operational route enables this until separately authorized.
    """
    if (
        settings.ENVIRONMENT != "development"
        or not settings.DEBUG
        or os.environ.get(
            "GECC_SANDBOX_COMPLETION_RETENTION_ENABLED", ""
        ) != "1"
    ):
        raise ValidationError("Completion retention is disabled.")

    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or actor.role != Role.COMPTROLLER
        or challenge is None
        or challenge.actor_id != actor.pk
        or challenge.consumed_at is None
    ):
        raise PermissionDenied("Authenticated OAuth reviewer required.")

    bundle = validated_pdf_bundle(evidence)

    try:
        canonical_attempt = str(UUID(attempt_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Canonical attempt ID required.") from None

    if attempt_id != canonical_attempt:
        raise ValidationError("Canonical attempt ID required.")

    attempt = CompletionEnvelopeAttempt.objects.select_related(
        "release_package__plan__msr__project"
    ).get(pk=canonical_attempt)

    package = attempt.release_package
    project = Project.objects.select_for_update().get(
        pk=package.plan.msr.project_id
    )

    if (
        project.state == "CANCELLED"
        or project.current_approved_id != package.plan.msr_id
        or package.plan.msr.status != "APPROVED"
        or package.plan.group not in (
            "COMPLETION_FINANCED",
            "COMPLETION_NON_FINANCED",
        )
        or package.plan.group != (
            "COMPLETION_" +
            str(package.plan.msr.snapshot.get("financing_type", ""))
        )
        or attempt.state != "SENT_UNCHECKED"
        or attempt.first_send_started_at is None
        or evidence.get("account_id") != attempt.provider_account_id
        or evidence.get("envelope_id") != attempt.provider_envelope_id
    ):
        raise ValidationError("Current approved envelope binding changed.")

    from . import release

    release.validate_package(package, check_current=True)
    if release.status(package).get("status") != "APPROVED":
        raise ValidationError("Current release approval is required.")

    if CompletionSignatureVerification.objects.filter(
        release_package=package
    ).exists():
        raise ValidationError(
            "Existing completion verification requires independent review."
        )

    preview = package.plan.review.get("envelope_preview")
    expected_documents = (
        preview.get("documents")
        if isinstance(preview, dict)
        else None
    )

    if not isinstance(expected_documents, list):
        raise ValidationError("Approved signed-document manifest missing.")

    names = {
        item["documentId"]: item["name"]
        for item in expected_documents
        if isinstance(item, dict)
        and isinstance(item.get("documentId"), str)
        and isinstance(item.get("name"), str)
    }

    expected_ids = set(names) | {"certificate"}
    if {item[0] for item in bundle} != expected_ids:
        raise ValidationError("Signed-document identities changed.")

    context = challenge.context
    if not isinstance(context, dict) or any(
        context.get(key) != value
        for key, value in {
            "operation": "SANDBOX_COMPLETION_READ",
            "completion_attempt_id": str(attempt.pk),
            "release_package_id": str(package.pk),
            "release_package_digest": package.digest,
            "project_id": str(project.pk),
            "msr_id": str(package.plan.msr_id),
            "account_id": attempt.provider_account_id,
            "envelope_id": attempt.provider_envelope_id,
        }.items()
    ):
        raise ValidationError("OAuth callback binding changed.")

    metadata = {
        "environment": "DOCUSIGN_SANDBOX",
        "status": "PROVIDER_READ_RETAINED_NOT_COMPLETION_AUTHORITY",
        "project_id": str(project.pk),
        "msr_id": str(package.plan.msr_id),
        "release_package_id": str(package.pk),
        "release_package_digest": package.digest,
        "attempt_id": str(attempt.pk),
        "oauth_challenge_id": str(challenge.pk),
        "account_id": attempt.provider_account_id,
        "envelope_id": attempt.provider_envelope_id,
        "completed_at": evidence.get("completed_at"),
        "signers": evidence.get("signers"),
        "pdf_manifest": evidence.get("pdf_manifest"),
        "completion_authorized": False,
        "receipt_email_authenticated": False,
    }

    verification = CompletionSignatureVerification.objects.create(
        release_package=package,
        verified_by=actor,
        provider_account_id=attempt.provider_account_id,
        provider_envelope_id=attempt.provider_envelope_id,
        evidence=metadata,
        digest=canonical_hash(metadata),
    )

    for document_id, digest, content in bundle:
        filename = (
            "DocuSign-Certificate-of-Completion.pdf"
            if document_id == "certificate"
            else names[document_id]
        )
        CompletionSignatureDocument.objects.create(
            verification=verification,
            document_id=document_id,
            kind=(
                "DOCUSIGN_AUDIT"
                if document_id == "certificate"
                else package.plan.group
            ),
            filename=filename[:250],
            content=content,
            pdf_sha256=digest,
        )

    audit(
        actor,
        "completion_signature.sandbox_provider_read_retained",
        project.pk,
        {
            "verification_id": str(verification.pk),
            "release_package_id": str(package.pk),
            "oauth_challenge_id": str(challenge.pk),
            "pdf_hashes": [item[1] for item in bundle],
            "provider_read_retained": True,
            "receipt_email_authenticated": False,
            "completion_authorized": False,
        },
    )

    return verification
