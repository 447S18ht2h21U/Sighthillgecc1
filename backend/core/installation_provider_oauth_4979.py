"""Development-only OAuth handoff for Installation Inspection readback.

The standard DocuSign OAuth callback validates the account and supplies
an ephemeral access token. This operation NEVER receives authorization
to send envelopes, never stores the bearer, and cannot certify signer
identity or authorize project completion.

A successful readback establishes that the authenticated sandbox account
returned bytes matching the already retained UNVERIFIED documents.
It does not replace provider signature/date verification.
"""
import os
from hashlib import sha256
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from . import docusign
from .documents import canonical_hash
from .services import audit
from .models import (
    Project, ProjectEvidence, User, Role,
    InstallationInspectionEvidence4969,
)
from .installation_envelope_binding_4976 import KIND
from .installation_evidence_retention_4969 import (
    verify_retained_inspection_bytes,
)
from .installation_provider_readback_4972 import (
    retrieve_inspection_sandbox_evidence,
)

OPERATION = "SANDBOX_INSPECTION_READ"


def _uuid(value):
    if type(value) is not str:
        raise ValidationError("Canonical UUID required.")
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Canonical UUID required.") from None
    return value


def _gate(actor):
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get("GECC_IM_OAUTH_READ_ENABLED") != "1"
        or os.environ.get("GECC_IM_PROVIDER_READBACK_ENABLED") != "1"
    ):
        raise PermissionDenied("Inspection OAuth readback disabled.")

    if (
        actor is None
        or not getattr(actor, "pk", None)
        or getattr(actor, "is_active", False) is not True
        or getattr(actor, "role", None) != Role.COMPTROLLER
    ):
        raise PermissionDenied("Comptroller sandbox reviewer required.")

    reviewer = User.objects.filter(
        pk=actor.pk, is_active=True, role=Role.COMPTROLLER
    ).first()
    if reviewer is None:
        raise PermissionDenied("Active Comptroller required.")
    return reviewer


def _binding(*, reviewer, project_id, binding_id, account_id=None):
    project = (
        Project.objects.select_related("current_approved")
        .filter(pk=project_id)
        .first()
    )
    if project is None or project.state == "CANCELLED":
        raise ValidationError("Active project required.")

    msr = project.current_approved
    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
    ):
        raise ValidationError("Current approved MSR required.")

    evidence = ProjectEvidence.objects.filter(
        pk=binding_id, msr=msr, kind=KIND
    ).first()
    if evidence is None or type(evidence.data) is not dict:
        raise ValidationError("Inspection envelope association missing.")

    data = evidence.data
    if (
        evidence.digest != canonical_hash(data)
        or data.get("state") != "ENVELOPE_ASSOCIATION_UNVERIFIED"
        or data.get("provider_authenticated") is not False
        or data.get("signer_verified") is not False
        or data.get("signed_date_verified") is not False
        or data.get("completion_authorized") is not False
        or data.get("project_id") != str(project.pk)
        or data.get("msr_id") != str(msr.pk)
        or data.get("msr_version") != str(msr.number)
    ):
        raise ValidationError("Inspection envelope association invalid.")

    account = _uuid(data.get("provider_account_id"))
    envelope_id = _uuid(data.get("provider_envelope_id"))
    if account_id is not None and account != _uuid(account_id):
        raise ValidationError("Provider account identity changed.")

    retained = InstallationInspectionEvidence4969.objects.filter(
        pk=data.get("retained_inspection_id"), msr=msr
    ).first()
    if retained is None:
        raise ValidationError("Retained inspection evidence missing.")

    integrity = verify_retained_inspection_bytes(retained)
    if (
        integrity.get("integrity_verified") is not True
        or integrity.get("provider_authenticated") is not False
        or retained.purported_envelope_id != envelope_id
        or retained.bundle_digest != data.get("retained_bundle_sha256")
        or retained.signed_pdf_sha256 != data.get("signed_pdf_sha256")
        or retained.certificate_sha256 != data.get("certificate_sha256")
        or retained.source_data.get("project_id") != str(project.pk)
        or retained.source_data.get("msr_id") != str(msr.pk)
        or retained.source_data.get("state") != "UNVERIFIED_RETAINED"
    ):
        raise ValidationError("Inspection retention binding invalid.")

    configured = docusign.configuration()
    if (
        type(configured) is not dict
        or configured.get("blockers")
        or configured.get("account_id") != account
        or docusign.BASE_URI != "https://demo.docusign.net"
    ):
        raise PermissionDenied("Configured sandbox account mismatch.")

    return project, evidence, retained, account, envelope_id


def begin(*, actor, project_id, binding_id, session_key):
    """Start an OAuth challenge only; perform NO envelope operations."""
    reviewer = _gate(actor)
    project, binding, retained, account, envelope_id = _binding(
        reviewer=reviewer,
        project_id=project_id,
        binding_id=binding_id,
    )
    if type(session_key) is not str or not session_key:
        raise PermissionDenied("Authenticated GECC session required.")

    # docusign.begin owns state, expiry, session binding, auditing
    # and the provider's authorization URL.
    response = docusign.begin(
        reviewer,
        session_key,
        context={
            "operation": OPERATION,
            "project_id": str(project.pk),
            "binding_id": str(binding.pk),
            "binding_digest": binding.digest,
            "retained_inspection_id": str(retained.pk),
            "account_id": account,
            "envelope_id": envelope_id,
            "reviewer_id": str(reviewer.pk),
            "send_enabled": False,
        },
    )
    return {
        **response,
        "operation": OPERATION,
        "send_enabled": False,
        "provider_signature_verified": False,
        "project_completion_authorized": False,
    }


def _screen_recipient_metadata(readback):
    """Screen provider metadata without authenticating signer identity."""
    from datetime import datetime, timezone

    summary = getattr(readback, "envelope_summary", None)
    recipients = getattr(readback, "recipient_summary", None)

    if type(summary) is not dict or type(recipients) is not dict:
        raise ValidationError("Provider recipient metadata missing.")

    signers = recipients.get("signers")
    if (
        type(signers) is not list
        or len(signers) != 1
        or type(signers[0]) is not dict
    ):
        raise ValidationError("Exactly one recipient signer required.")

    signer = signers[0]
    if (
        signer.get("recipientId") != "1"
        or signer.get("status") != "completed"
        or type(signer.get("name")) is not str
        or not signer["name"].strip()
        or type(signer.get("email")) is not str
        or not signer["email"].strip()
    ):
        raise ValidationError("Completed recipient metadata inconsistent.")

    def parse_date(value):
        if type(value) is not str or not value or len(value) > 64:
            raise ValidationError("Provider signing timestamp missing.")
        try:
            date = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError:
            raise ValidationError(
                "Malformed provider signing timestamp."
            ) from None

        if date.tzinfo is None or date.utcoffset() is None:
            raise ValidationError(
                "Timezone-aware provider timestamp required."
            )

        return date.astimezone(timezone.utc)

    signed = parse_date(signer.get("signedDateTime"))
    completed = parse_date(summary.get("completedDateTime"))

    if signed > completed:
        raise ValidationError(
            "Envelope completion precedes recipient signing."
        )

    previous = None
    for field in ("sentDateTime", "deliveredDateTime"):
        value = signer.get(field)
        if value is None:
            continue
        current = parse_date(value)
        if current > signed or (
            previous is not None and current < previous
        ):
            raise ValidationError(
                "Recipient event chronology inconsistent."
            )
        previous = current

    return None


def _screen_intended_manager(readback, retained):
    """Match reported recipient to the retained intended manager.

    This is an identity-consistency check, NOT proof that the
    intended person actually signed.
    """
    metadata = getattr(retained, "source_data", None)
    if type(metadata) is not dict:
        raise ValidationError("Retained manager identity missing.")

    manager_id = _uuid(metadata.get("intended_manager_id"))
    manager = User.objects.filter(
        pk=manager_id,
        is_active=True,
        role=Role.INSTALLATION_MANAGER,
    ).first()

    if manager is None:
        raise ValidationError(
            "Intended Installation Manager is not active."
        )

    recipients = getattr(readback, "recipient_summary", None)
    signers = (
        recipients.get("signers")
        if type(recipients) is dict else None
    )

    if (
        type(signers) is not list
        or len(signers) != 1
        or type(signers[0]) is not dict
    ):
        raise ValidationError(
            "Exactly one returned Installation Manager required."
        )

    returned = signers[0]
    expected_name = manager.get_full_name().strip()
    expected_email = manager.email.strip()

    if (
        not expected_name
        or not expected_email
        or type(returned.get("name")) is not str
        or type(returned.get("email")) is not str
        or returned["name"] != expected_name
        or returned["email"].strip().casefold()
        != expected_email.casefold()
    ):
        raise ValidationError(
            "DocuSign recipient differs from intended manager."
        )

    # A matching name and email do not authenticate the signer.
    return None


def _screen_inspection_response_tabs(readback):
    """Check five returned responses; do not verify inspection findings."""
    from .installation_inspection_form_4945 import INSPECTION_IDS

    tabs = getattr(readback, "recipient_tabs", None)
    if type(tabs) is not dict:
        raise ValidationError("Inspection recipient tabs missing.")

    groups = tabs.get("radioGroupTabs")
    if type(groups) is not list or len(groups) != len(INSPECTION_IDS):
        raise ValidationError("Exactly five inspection responses required.")

    seen = set()
    for group in groups:
        if type(group) is not dict:
            raise ValidationError("Invalid inspection question group.")

        name = group.get("groupName")
        if type(name) is not str or name not in INSPECTION_IDS:
            raise ValidationError("Unexpected inspection question.")
        if name in seen:
            raise ValidationError("Duplicate inspection question.")
        seen.add(name)

        radios = group.get("radios")
        if type(radios) is not list or len(radios) != 2:
            raise ValidationError("Two inspection choices required.")

        values = set()
        selected_count = 0
        for radio in radios:
            if type(radio) is not dict:
                raise ValidationError("Invalid inspection choice.")

            value = radio.get("value")
            selected = radio.get("selected")

            if (
                type(value) is not str
                or not value
                or value in values
                or selected not in ("true", "false")
            ):
                raise ValidationError("Invalid inspection choice data.")

            values.add(value)
            if selected == "true":
                selected_count += 1

        if selected_count != 1:
            raise ValidationError(
                "Exactly one inspection answer required."
            )

    if seen != set(INSPECTION_IDS):
        raise ValidationError("Incomplete inspection question set.")

    # No claim about the substantive validity of the answers.
    return None


def _screen_provider_audit_history(readback):
    """Require a shaped provider audit history without verifying signing.

    These are untrusted observations returned through an authenticated
    GET. Their presence is not evidence of actual signer identity.
    """
    history = getattr(readback, "audit_events", None)
    if type(history) is not dict:
        raise ValidationError("Provider audit history missing.")

    events = history.get("auditEvents")
    if (
        type(events) is not list
        or not 1 <= len(events) <= 1000
    ):
        raise ValidationError("Provider audit events missing.")

    for event in events:
        if type(event) is not dict:
            raise ValidationError("Malformed provider audit event.")

        fields = event.get("eventFields")
        if type(fields) is not list or not fields:
            raise ValidationError("Provider audit event fields missing.")

        if len(fields) > 100:
            raise ValidationError("Excessive provider audit fields.")

        for field in fields:
            if type(field) is not dict:
                raise ValidationError("Malformed provider audit field.")

            name = field.get("name")
            if (
                type(name) is not str
                or not name.strip()
                or len(name) > 128
            ):
                raise ValidationError("Invalid provider audit field name.")

            value = field.get("value")
            if (
                value is not None
                and (type(value) is not str or len(value) > 4096)
            ):
                raise ValidationError("Invalid provider audit field value.")

    # Deliberately do not assert signer, certificate, or date trust.
    return None


def _screen_audit_chronology(readback):
    """Screen audit-event chronology without establishing signature trust."""
    from datetime import datetime, timezone

    def timestamp(value):
        if type(value) is not str or not value or len(value) > 64:
            raise ValidationError("Audit timestamp missing.")

        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError:
            raise ValidationError(
                "Malformed audit timestamp."
            ) from None

        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValidationError(
                "Timezone-aware audit timestamp required."
            )

        return parsed.astimezone(timezone.utc)

    history = getattr(readback, "audit_events", None)
    summary = getattr(readback, "envelope_summary", None)
    recipients = getattr(readback, "recipient_summary", None)

    if (
        type(history) is not dict
        or type(summary) is not dict
        or type(recipients) is not dict
    ):
        raise ValidationError("Audit chronology evidence missing.")

    events = history.get("auditEvents")
    signers = recipients.get("signers")

    if (
        type(events) is not list
        or not events
        or type(signers) is not list
        or len(signers) != 1
        or type(signers[0]) is not dict
    ):
        raise ValidationError("Audit chronology incomplete.")

    signed = timestamp(signers[0].get("signedDateTime"))
    completed = timestamp(summary.get("completedDateTime"))

    if signed > completed:
        raise ValidationError(
            "Envelope completion precedes signing."
        )

    event_times = []

    for event in events:
        if type(event) is not dict:
            raise ValidationError("Malformed audit event.")

        fields = event.get("eventFields")
        if type(fields) is not list:
            raise ValidationError("Audit event fields missing.")

        log_times = [
            field.get("value")
            for field in fields
            if type(field) is dict
            and field.get("name") == "logTime"
        ]

        if len(log_times) != 1:
            raise ValidationError(
                "Exactly one timestamp required per audit event."
            )

        event_times.append(timestamp(log_times[0]))

    # Post-completion document-access events remain permissible.
    if not any(value <= completed for value in event_times):
        raise ValidationError(
            "Audit history does not overlap envelope timeline."
        )

    return None


def _screen_audit_action_consistency(readback):
    """Check provider audit actions without authenticating signatures."""
    history = getattr(readback, "audit_events", None)
    recipients = getattr(readback, "recipient_summary", None)
    if type(history) is not dict or type(recipients) is not dict:
        raise ValidationError("Audit action context missing.")

    events = history.get("auditEvents")
    signers = recipients.get("signers")
    if (
        type(events) is not list or not events
        or type(signers) is not list or len(signers) != 1
        or type(signers[0]) is not dict
    ):
        raise ValidationError("Audit action context invalid.")

    expected_name = signers[0].get("name")
    if type(expected_name) is not str or not expected_name.strip():
        raise ValidationError("Intended recipient name missing.")

    for event in events:
        if type(event) is not dict:
            raise ValidationError("Invalid audit action event.")
        fields = event.get("eventFields")
        if type(fields) is not list:
            raise ValidationError("Audit action fields missing.")

        actions = [
            item.get("value") for item in fields
            if type(item) is dict and item.get("name") == "Action"
        ]
        if (
            len(actions) != 1
            or type(actions[0]) is not str
            or not actions[0].strip()
            or len(actions[0]) > 128
        ):
            raise ValidationError("Exactly one audit action required.")

        # Only this explicit action is screened for user consistency.
        # Other vendor action labels are deliberately not classified.
        if actions[0] == "Signed":
            names = [
                item.get("value") for item in fields
                if type(item) is dict and item.get("name") == "UserName"
            ]
            if len(names) != 1 or names[0] != expected_name:
                raise ValidationError(
                    "Reported signing action recipient mismatch."
                )
    return None


def finish(actor, challenge, config, token):
    """Use validated callback token transiently; never persist it.

    This function is called ONLY by docusign.finish after OAuth
    callback state/session/account validation.
    """
    reviewer = _gate(actor)

    context = getattr(challenge, "context", None)
    if (
        type(context) is not dict
        or context.get("operation") != OPERATION
        or context.get("send_enabled") is not False
        or context.get("reviewer_id") != str(reviewer.pk)
        or getattr(challenge, "actor_id", None) != reviewer.pk
    ):
        raise PermissionDenied("OAuth operation context mismatch.")

    project, binding, retained, account, envelope_id = _binding(
        reviewer=reviewer,
        project_id=context.get("project_id"),
        binding_id=context.get("binding_id"),
        account_id=context.get("account_id"),
    )

    if (
        context.get("binding_digest") != binding.digest
        or context.get("retained_inspection_id") != str(retained.pk)
        or context.get("envelope_id") != envelope_id
        or type(config) is not dict
        or config.get("blockers")
        or config.get("account_id") != account
    ):
        raise PermissionDenied("OAuth association changed.")

    # The gateway receives the access token in memory. It uses a
    # fixed DocuSign sandbox host and strictly allowlisted GET paths.
    readback = retrieve_inspection_sandbox_evidence(
        actor=reviewer,
        account_id=account,
        envelope_id=envelope_id,
        bearer_token=token,
    )

    if (
        readback.account_id != account
        or readback.envelope_id != envelope_id
        or readback.envelope_summary.get("envelopeId") != envelope_id
        or readback.envelope_summary.get("status") != "completed"
        or readback.provider_signature_verified is not False
        or readback.completion_authorized is not False
        or readback.signed_pdf_sha256 != retained.signed_pdf_sha256
        or readback.certificate_sha256 != retained.certificate_sha256
        or sha256(readback.signed_pdf).hexdigest()
        != retained.signed_pdf_sha256
        or sha256(readback.certificate_pdf).hexdigest()
        != retained.certificate_sha256
        or readback.signed_pdf != bytes(retained.signed_pdf)
        or readback.certificate_pdf != bytes(retained.certificate_pdf)
    ):
        raise ValidationError(
            "Authenticated sandbox readback differs from retained evidence."
        )

    # Screen authenticated response metadata before success audit.
    # Metadata consistency is not proof of signer identity.
    _screen_recipient_metadata(readback)

    # Check against the manager identified by retained project evidence.
    # A match is necessary but never sufficient for signature trust.
    _screen_intended_manager(readback, retained)

    # Ensure five returned responses exist before the byte-match audit.
    # Completeness does not establish inspection approval or signature trust.
    _screen_inspection_response_tabs(readback)

    # Independently require provider audit history before success audit.
    # History presence does not prove a signer or validate a certificate.
    _screen_provider_audit_history(readback)

    # Correlate event chronology before the success audit.
    # This is not independent signature or certificate verification.
    _screen_audit_chronology(readback)

    # Check audit actions; never infer independent signature trust.
    _screen_audit_action_consistency(readback)

    # Provider-returned bytes match; signing remains unverified.
    # Never retain tokens, raw PDFs or signer personal information.
    audit(
        reviewer,
        "installation.inspection_sandbox_readback_bytes_matched",
        project.pk,
        {
            "project_id": str(project.pk),
            "binding_id": str(binding.pk),
            "retained_inspection_id": str(retained.pk),
            "account_id": account,
            "envelope_id": envelope_id,
            "signed_pdf_sha256": retained.signed_pdf_sha256,
            "certificate_sha256": retained.certificate_sha256,
            "audit_history_sha256": canonical_hash(
                readback.audit_events
            ),
            "status": "SANDBOX_READBACK_BYTES_MATCHED_SIGNER_UNVERIFIED",
            "provider_signature_verified": False,
            "signed_date_verified": False,
            "inspection_findings_verified": False,
            "trusted_installation_evidence": False,
            "receipt_issuance_authorized": False,
            "project_completion_authorized": False,
        },
    )

    # No claim of signing authenticity: recipient tabs, signer identity,
    # signed date and provider certificate verification remain separate.
    # No raw PDFs, tokens, or signer personal data are returned.
    return {
        "operation": OPERATION,
        "status": "SANDBOX_READBACK_BYTES_MATCHED_SIGNER_UNVERIFIED",
        "project_id": str(project.pk),
        "binding_id": str(binding.pk),
        "retained_inspection_id": str(retained.pk),
        "account_id": account,
        "envelope_id": envelope_id,
        "signed_pdf_sha256": retained.signed_pdf_sha256,
        "certificate_sha256": retained.certificate_sha256,
        "readback_bytes_match": True,
        "provider_signature_verified": False,
        "signed_date_verified": False,
        "inspection_findings_verified": False,
        "corrective_actions_created": False,
        "project_completion_authorized": False,
        "send_enabled": False,
    }
