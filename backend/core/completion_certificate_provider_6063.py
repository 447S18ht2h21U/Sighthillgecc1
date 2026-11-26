"""Controlled fictional Completion Certificate draft integration.

Reuses existing OAuth account verification and fixed sandbox transport.
No sending, operational signature trust or project completion authority.
"""

import os

from uuid import UUID

from django.db import connections, transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from . import docusign, sandbox

from .documents import canonical_hash

from .models import (
    DocusignChallenge,
    DocusignVerification,
    Project,
    ProjectEvidence,
    Role,
    User,
)

from .services import audit

from .completion_certificate_preparation_6048 import (
    prepare_project_certificate_preview,
)

from .completion_certificate_retention_6052 import (
    CERTIFICATE_EVIDENCE_KIND,
    approved_recipient,
)

from .completion_certificate_sandbox_package_6056 import (
    SANDBOX_PACKAGE_KIND,
    DESIGNATED_SANDBOX_RECIPIENT,
    sandbox_envelope_preview,
)

from .installation_inspection_transaction_6039 import (
    require_inspection_development_environment,
)


OPERATION = "SANDBOX_CERTIFICATE_DRAFT_6063"

FLAG = "GECC_CERTIFICATE_SANDBOX_DRAFT_ENABLED"

RESERVATION_KIND = "CERT_DRAFT_RESERVE_6063"

RESULT_KIND = "CERT_DRAFT_RESULT_6063"

OBSERVATION_KIND = "CERT_DRAFT_CHECK_6063"

PROJECT_ID = "be368760-9d10-4157-8e8c-2eb3a6ade90e"

PACKAGE_ID = "3836b95e-cf4c-49c0-8e0c-88b13f4fb88e"

PACKAGE_DIGEST = (
    "cd4d03103f4c4e0def574ae6071b32098"
    "fe24d5d844c2b134a3246e9a4446fd5"
)


def uuid_value(value):

    try:

        result = str(UUID(value))

    except (ValueError, TypeError, AttributeError):

        raise ValidationError(
            "Invalid provider identifier."
        ) from None

    if value != result:

        raise ValidationError(
            "Canonical provider identifier required."
        )

    return result


def authorize_context(actor, context):

    require_inspection_development_environment()

    if os.environ.get(FLAG) != "1":

        raise PermissionDenied(
            "Completion Certificate sandbox draft creation is disabled."
        )

    if any(
        os.environ.get(name) == "1"
        for name in (
            "GECC_COMMERCIAL_SANDBOX_SEND_ENABLED",
            "GECC_SANDBOX_SIGNING_SEND_ENABLED",
        )
    ):

        raise PermissionDenied(
            "Other sandbox sending operations must remain disabled."
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
        or context.get("recipient")
            != DESIGNATED_SANDBOX_RECIPIENT
        or context.get("fictional_confirmed") is not True
        or context.get("send_authorized") is not False
    ):

        raise PermissionDenied(
            "Exact fictional certificate authorization required."
        )

    return current


def single_evidence(project, kind):

    rows = list(
        ProjectEvidence.objects.filter(
            msr__project=project,
            kind=kind,
        )[:2]
    )

    if len(rows) > 1:

        raise ValidationError(
            "Conflicting draft records require manual review."
        )

    return rows[0] if rows else None


def current_package(actor):

    require_inspection_development_environment()

    prepared = prepare_project_certificate_preview(
        actor=actor,
        project_id=PROJECT_ID,
    )

    project = (
        Project.objects.select_for_update()
        .select_related("current_approved")
        .get(pk=PROJECT_ID)
    )

    msr = project.current_approved

    if (
        msr is None
        or str(msr.pk) != prepared["msr_id"]
        or msr.status != "APPROVED"
        or project.state == "CANCELLED"
    ):

        raise ValidationError(
            "Current approved fictional project required."
        )

    package = single_evidence(
        project,
        SANDBOX_PACKAGE_KIND,
    )

    certificate = single_evidence(
        project,
        CERTIFICATE_EVIDENCE_KIND,
    )

    if (
        package is None
        or certificate is None
        or package.msr_id != msr.pk
        or certificate.msr_id != msr.pk
        or str(package.pk) != PACKAGE_ID
        or package.digest != PACKAGE_DIGEST
        or certificate.data.get("prepared_by")
            != str(certificate.created_by_id)
        or certificate.data.get("recipient")
            != approved_recipient(msr.snapshot)
    ):

        raise ValidationError(
            "Exact retained fictional signing package required."
        )

    for key in (
        "project_id",
        "msr_id",
        "msr_version",
        "snapshot_sha256",
        "inspection_id",
        "inspection_digest",
        "manifest_sha256",
        "reference_sha256",
        "kind",
        "identity",
    ):

        if certificate.data.get(key) != prepared[key]:

            raise ValidationError(
                "Current certificate evidence changed."
            )

    for key in (
        "project_id",
        "msr_id",
        "snapshot_sha256",
        "inspection_id",
        "inspection_digest",
    ):

        if package.data.get(key) != prepared[key]:

            raise ValidationError(
                "Current signing-package evidence changed."
            )

    payload = sandbox_envelope_preview(
        package=package,
        certificate=certificate,
    )

    if payload.get("status") != "created":

        raise ValidationError(
            "Only unsent drafts are permitted."
        )

    return project, msr, package, certificate, payload


def context_for(package, certificate, config):

    return {
        "operation": OPERATION,
        "project_id": PROJECT_ID,
        "package_id": str(package.pk),
        "package_digest": package.digest,
        "certificate_id": str(certificate.pk),
        "certificate_digest": certificate.digest,
        "pdf_sha256": certificate.data["pdf_sha256"],
        "account_id": config["account_id"],
        "recipient": DESIGNATED_SANDBOX_RECIPIENT,
        "fictional_confirmed": True,
        "send_authorized": False,
    }


@transaction.atomic
def begin(
    *,
    actor,
    session_key,
    project_id,
    expected_package_id,
    expected_package_digest,
    confirmed,
):

    if (
        str(project_id) != PROJECT_ID
        or expected_package_id != PACKAGE_ID
        or expected_package_digest != PACKAGE_DIGEST
        or confirmed is not True
    ):

        raise ValidationError(
            "Confirm the exact retained fictional signing package."
        )

    project, msr, package, certificate, payload = (
        current_package(actor)
    )

    config = docusign.configuration()

    if config["blockers"]:

        raise ValidationError(
            {"configuration": config["blockers"]}
        )

    context = context_for(
        package,
        certificate,
        config,
    )

    current = authorize_context(
        actor,
        context,
    )

    if single_evidence(project, RESERVATION_KIND):

        raise ValidationError(
            "A draft attempt already exists. "
            "Inspect it before proceeding."
        )

    result = docusign.begin(
        current,
        session_key,
        context,
    )

    return {
        **result,
        "operation": OPERATION,
        "send_authorized": False,
        "completion_authorized": False,
    }


@transaction.atomic
def reserve(
    *,
    actor,
    challenge,
    config,
):

    current = authorize_context(
        actor,
        challenge.context,
    )

    project, msr, package, certificate, payload = (
        current_package(current)
    )

    fresh_config = docusign.configuration()

    if (
        fresh_config["blockers"]
        or config["account_id"]
            != fresh_config["account_id"]
        or challenge.context != context_for(
            package,
            certificate,
            fresh_config,
        )
        or challenge.configuration_digest
            != docusign.configuration_digest(fresh_config)
    ):

        raise ValidationError(
            "Certificate OAuth configuration or binding changed."
        )

    stored = (
        DocusignChallenge.objects.select_for_update()
        .get(pk=challenge.pk)
    )

    if (
        stored.actor_id != current.pk
        or stored.consumed_at is None
        or stored.expires_at <= timezone.now()
        or stored.context != challenge.context
        or stored.configuration_digest
            != challenge.configuration_digest
    ):

        raise PermissionDenied(
            "Consumed current OAuth challenge required."
        )

    proof = DocusignVerification.objects.filter(
        actor=current,
        challenge=stored,
    ).first()

    if (
        proof is None
        or canonical_hash(proof.identity) != proof.digest
        or proof.identity.get("environment") != "SANDBOX"
        or proof.identity.get("account_id")
            != config["account_id"]
        or proof.identity.get("base_uri")
            != "https://demo.docusign.net"
        or proof.identity.get("purpose") != OPERATION
        or proof.identity.get("tokens_retained") is not False
    ):

        raise PermissionDenied(
            "Authenticated sandbox account proof required."
        )

    if any(
        single_evidence(project, kind)
        for kind in (
            RESERVATION_KIND,
            RESULT_KIND,
            OBSERVATION_KIND,
        )
    ):

        raise ValidationError(
            "A certificate draft attempt already exists. "
            "Never create a duplicate."
        )

    data = {
        **challenge.context,
        "state": "PROVIDER_OUTCOME_UNKNOWN",
        "challenge_id": str(stored.pk),
        "verification_id": str(proof.pk),
        "msr_id": str(msr.pk),
        "reserved_by": str(current.pk),
        "payload_digest": canonical_hash(payload),
        "reserved_at": timezone.now().isoformat(),
        "signed": False,
        "completion_authorized": False,
    }

    reservation = ProjectEvidence.objects.create(
        msr=msr,
        kind=RESERVATION_KIND,
        created_by=current,
        data=data,
        digest=canonical_hash(data),
    )

    audit(
        current,
        "installation.certificate_sandbox_draft_reserved",
        project.pk,
        {
            "reservation_id": str(reservation.pk),
            "package_digest": package.digest,
            "send_authorized": False,
        },
    )

    return reservation, payload


@transaction.atomic
def retain_result(
    *,
    actor,
    reservation,
    envelope_id,
    provider_status,
):

    original = ProjectEvidence.objects.get(
        pk=reservation.pk,
        kind=RESERVATION_KIND,
    )

    project = Project.objects.select_for_update().get(
        pk=original.msr.project_id,
    )

    if (
        original.digest != canonical_hash(original.data)
        or original.created_by_id != actor.pk
        or original.data["state"]
            != "PROVIDER_OUTCOME_UNKNOWN"
        or single_evidence(project, RESULT_KIND)
    ):

        raise ValidationError(
            "Draft reservation requires reconciliation."
        )

    data = {
        "reservation_id": str(original.pk),
        "reservation_digest": original.digest,
        "package_digest": original.data["package_digest"],
        "account_id": original.data["account_id"],
        "envelope_id": uuid_value(envelope_id),
        "provider_status": provider_status,
        "state": "CREATED_UNVALIDATED",
        "send_authorized": False,
        "signed": False,
        "completion_authorized": False,
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
        "installation.certificate_sandbox_draft_identified",
        project.pk,
        {
            "reservation_id": str(original.pk),
            "result_id": str(result.pk),
            "envelope_id": envelope_id,
            "send_authorized": False,
        },
    )

    return result


def validate_provider_draft(
    expected,
    summary,
    recipients,
    documents,
    envelope_id,
):

    if (
        summary.get("status") != "created"
        or summary.get("envelopeId") != envelope_id
    ):

        raise ValidationError(
            "Expected unsent certificate draft required."
        )

    signers = recipients.get("signers")

    if (
        type(signers) is not list
        or len(signers) != 1
    ):

        raise ValidationError(
            "Exactly one customer signer required."
        )

    for key, value in recipients.items():

        if (
            key != "signers"
            and isinstance(value, list)
            and value
        ):

            raise ValidationError(
                "Unexpected additional recipients."
            )

    signer = signers[0]

    target = expected["recipients"]["signers"][0]

    for key in (
        "recipientId",
        "routingOrder",
        "name",
        "email",
    ):

        if signer.get(key) != target[key]:

            raise ValidationError(
                "Provider signer identity changed."
            )

    tabs = signer.get("tabs")

    if type(tabs) is not dict:

        raise ValidationError(
            "Provider signing fields unavailable."
        )

    for group, entries in target["tabs"].items():

        actual = tabs.get(group)

        if (
            type(actual) is not list
            or len(actual) != len(entries)
        ):

            raise ValidationError(
                "Provider signing-field count changed."
            )

        for entry in entries:

            matches = [
                item for item in actual
                if all(
                    str(item.get(key, "")) == str(entry[key])
                    for key in (
                        "documentId",
                        "pageNumber",
                        "xPosition",
                        "yPosition",
                        "tabLabel",
                    )
                )
            ]

            if len(matches) != 1:

                raise ValidationError(
                    "Provider signing-field position changed."
                )

            if (
                entry.get("optional") == "false"
                and str(
                    matches[0].get("optional", "")
                ).lower() != "false"
            ):

                raise ValidationError(
                    "Provider customer signature is not mandatory."
                )

    if any(
        isinstance(value, list) and value
        for key, value in tabs.items()
        if key not in target["tabs"]
    ):

        raise ValidationError(
            "Unexpected additional signing fields."
        )

    rows = documents.get("envelopeDocuments")

    if type(rows) is not list:

        raise ValidationError(
            "Provider document inventory unavailable."
        )

    regular = [
        row for row in rows
        if row.get("documentId") != "certificate"
    ]

    if (
        len(regular) != 1
        or regular[0].get("documentId") != "1"
        or regular[0].get("name")
            != expected["documents"][0]["name"]
    ):

        raise ValidationError(
            "Provider certificate inventory changed."
        )

    return {
        "recipient_metadata_verified": True,
        "tab_metadata_verified": True,
        "document_inventory_verified": True,
        "provider_pdf_content_verified": False,
        "visual_layout_verified": False,
    }


@transaction.atomic
def retain_observation(
    *,
    actor,
    result,
    checks,
):

    project, msr, package, certificate, payload = (
        current_package(actor)
    )

    if (
        result.msr_id != msr.pk
        or result.digest != canonical_hash(result.data)
        or result.data["package_digest"] != package.digest
        or result.data["provider_status"] != "created"
        or single_evidence(project, OBSERVATION_KIND)
    ):

        raise ValidationError(
            "Provider observation binding requires review."
        )

    data = {
        "result_id": str(result.pk),
        "result_digest": result.digest,
        "envelope_id": result.data["envelope_id"],
        "account_id": result.data["account_id"],
        "package_digest": package.digest,
        "state": "DRAFT_METADATA_VALIDATED",
        "checks": checks,
        "observed_at": timezone.now().isoformat(),
        "send_authorized": False,
        "signed": False,
        "completion_authorized": False,
    }

    record = ProjectEvidence.objects.create(
        msr=msr,
        kind=OBSERVATION_KIND,
        created_by=actor,
        data=data,
        digest=canonical_hash(data),
    )

    audit(
        actor,
        "installation.certificate_sandbox_draft_checked",
        project.pk,
        {
            "observation_id": str(record.pk),
            "envelope_id": data["envelope_id"],
            "send_authorized": False,
        },
    )

    return record


@sensitive_variables()
def finish(actor, challenge, config, token):

    if connections["default"].in_atomic_block:

        raise ValidationError(
            "Provider operation requires committed reservation."
        )

    if (
        type(token) is not str
        or not 16 <= len(token) <= 16384
        or any(character.isspace() for character in token)
    ):

        raise PermissionDenied(
            "Transient authenticated OAuth token required."
        )

    reservation, payload = reserve(
        actor=actor,
        challenge=challenge,
        config=config,
    )

    account = uuid_value(config["account_id"])

    # Reservation is committed before external I/O.
    # A timeout must never result in an automatic retry.

    payload["transactionId"] = str(reservation.pk)

    try:

        response = sandbox.provider(
            account,
            "",
            token,
            payload=payload,
        )

        envelope_id = uuid_value(
            response.get("envelopeId")
        )

        result = retain_result(
            actor=actor,
            reservation=reservation,
            envelope_id=envelope_id,
            provider_status=str(
                response.get("status", "")
            )[:32],
        )

        if response.get("status") != "created":

            raise ValidationError(
                "Provider did not confirm an unsent draft."
            )

        summary = sandbox.provider(
            account,
            envelope_id,
            token,
        )

        recipients = sandbox.provider(
            account,
            envelope_id,
            token,
            resource="/recipients?include_tabs=true",
        )

        documents = sandbox.provider(
            account,
            envelope_id,
            token,
            resource="/documents",
        )

        checks = validate_provider_draft(
            payload,
            summary,
            recipients,
            documents,
            envelope_id,
        )

        after = sandbox.provider(
            account,
            envelope_id,
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
                "Provider draft changed during inspection."
            )

        observation = retain_observation(
            actor=actor,
            result=result,
            checks=checks,
        )

    except Exception:

        raise ValidationError(
            "Certificate draft requires reconciliation. "
            "Do not create another copy. "
            "No send operation was requested."
        ) from None

    return {
        "status": "SANDBOX_CERTIFICATE_DRAFT_VALIDATED",
        "envelope_id": envelope_id,
        "reservation_id": str(reservation.pk),
        "observation_id": str(observation.pk),
        "metadata_verified": True,
        "visual_layout_verified": False,
        "send_authorized": False,
        "completion_authorized": False,
        "tokens_retained": False,
        "message": (
            "Unsent fictional certificate draft created. "
            "Visual review is still required. "
            "No invitation was sent."
        ),
    }
