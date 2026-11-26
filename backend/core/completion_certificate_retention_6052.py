"""Retain exact fictional Completion Certificate bytes.

Document preparation and signing-recipient authorization
are separate operations.

Missing recipient information must never grant sending
authority or require historical MSR modification.
"""

from base64 import b64encode, b64decode
from binascii import Error as Base64Error
from hashlib import sha256
from io import BytesIO

from pypdf import PdfReader

from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)

from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from rest_framework.exceptions import ValidationError

from .documents import canonical_hash

from .models import ProjectEvidence

from .services import audit

from .distributor_invoice_services_5999 import _project

from .completion_certificate_preparation_6048 import (
    prepare_project_certificate_preview,
)

from .installation_inspection_transaction_6039 import (
    require_inspection_development_environment,
)


CERTIFICATE_EVIDENCE_KIND = "CERT_PREVIEW_6052"

MAX_PDF_BYTES = 15 * 1024 * 1024

FALSE_AUTHORITY_FIELDS = (
    "signed",
    "recipient_authorized",
    "trusted_installation_evidence",
    "installation_acceptance_authorized",
    "certificate_send_authorized",
    "customer_document_release_authorized",
    "financial_posting_authorized",
    "completion_authorized",
)


def approved_recipient(snapshot):

    if type(snapshot) is not dict:

        raise ValidationError(
            "Approved customer information is required."
        )

    name = snapshot.get("customer")

    if (
        type(name) is not str
        or not name.strip()
        or len(name) > 250
        or any(
            ord(character) < 32
            or ord(character) == 127
            for character in name
        )
    ):

        raise ValidationError(
            "Approved customer name requires review."
        )

    result = {
        "name": name.strip(),
        "email": None,
        "source": "CURRENT_APPROVED_MSR",
        "status": "RECIPIENT_EMAIL_REQUIRED",
        "authorized": False,
    }

    email = snapshot.get("customer_email")

    if email is None or (
        type(email) is str
        and not email.strip()
    ):

        return result

    if (
        type(email) is not str
        or len(email) > 254
        or any(
            ord(character) < 32
            or ord(character) == 127
            for character in email
        )
    ):

        result["status"] = "RECIPIENT_EMAIL_REVIEW_REQUIRED"

        return result

    email = email.strip()

    try:

        validate_email(email)

    except DjangoValidationError:

        result["status"] = "RECIPIENT_EMAIL_REVIEW_REQUIRED"

        return result

    result["email"] = email

    domain = email.rsplit("@", 1)[-1].casefold()

    if (
        domain.endswith(".invalid")
        or domain.endswith(".test")
        or domain.endswith(".localhost")
        or domain in {
            "localhost",
            "example.com",
            "example.net",
            "example.org",
        }
        or domain.endswith(".example")
    ):

        result["status"] = "PLACEHOLDER_EMAIL_REVIEW_REQUIRED"

    else:

        result["status"] = "RECIPIENT_AUTHORIZATION_REQUIRED"

    return result


def validate_recipient_record(recipient):

    if type(recipient) is not dict:

        raise ValidationError(
            "Retained recipient information is invalid."
        )

    if set(recipient) != {
        "name",
        "email",
        "source",
        "status",
        "authorized",
    }:

        raise ValidationError(
            "Unexpected retained recipient fields."
        )

    if (
        recipient["source"] != "CURRENT_APPROVED_MSR"
        or recipient["authorized"] is not False
        or type(recipient["name"]) is not str
        or not recipient["name"].strip()
        or len(recipient["name"]) > 250
        or any(
            ord(character) < 32
            or ord(character) == 127
            for character in recipient["name"]
        )
    ):

        raise ValidationError(
            "Retained recipient information requires review."
        )

    status = recipient["status"]

    email = recipient["email"]

    if status in {
        "RECIPIENT_EMAIL_REQUIRED",
        "RECIPIENT_EMAIL_REVIEW_REQUIRED",
    }:

        if email is not None:

            raise ValidationError(
                "Unresolved recipient must not supply "
                "a signing email address."
            )

        return

    if status not in {
        "RECIPIENT_AUTHORIZATION_REQUIRED",
        "PLACEHOLDER_EMAIL_REVIEW_REQUIRED",
    }:

        raise ValidationError(
            "Unexpected recipient authorization status."
        )

    expected = approved_recipient({
        "customer": recipient["name"],
        "customer_email": email,
    })

    if expected != recipient:

        raise ValidationError(
            "Retained recipient information is inconsistent."
        )


def validate_retained_certificate(
    *,
    payload,
    digest,
):

    if type(payload) is not dict:

        raise ValidationError(
            "Retained certificate evidence is invalid."
        )

    if canonical_hash(payload) != digest:

        raise ValidationError(
            "Retained certificate evidence fingerprint mismatch."
        )

    if (
        payload.get("purpose")
            != "FICTIONAL_COMPLETION_CERTIFICATE_PREPARATION"
        or payload.get("fictional_preview") is not True
        or payload.get("status")
            != "PREPARED_NOT_AUTHORIZED"
    ):

        raise ValidationError(
            "Unexpected retained certificate purpose."
        )

    for field in FALSE_AUTHORITY_FIELDS:

        if payload.get(field) is not False:

            raise ValidationError(
                "Unexpected certificate authorization state: "
                + field
            )

    if payload.get("kind") not in {
        "COMPLETION_FINANCED",
        "COMPLETION_NON_FINANCED",
    }:

        raise ValidationError(
            "Retained certificate classification is invalid."
        )

    recipient = payload.get("recipient")

    validate_recipient_record(recipient)

    identity = payload.get("identity")

    if (
        type(identity) is not dict
        or identity.get("customer_name")
            != recipient["name"]
    ):

        raise ValidationError(
            "Retained certificate and recipient names differ."
        )

    encoded = payload.get("pdf_base64")

    if (
        type(encoded) is not str
        or len(encoded) > 4 * ((MAX_PDF_BYTES + 2) // 3)
    ):

        raise ValidationError(
            "Retained certificate exceeds its allowed size."
        )

    try:

        content = b64decode(
            encoded,
            validate=True,
        )

    except (Base64Error, ValueError):

        raise ValidationError(
            "Retained certificate encoding is invalid."
        ) from None

    if (
        not content.startswith(b"%PDF-")
        or len(content) > MAX_PDF_BYTES
        or type(payload.get("pdf_size")) is not int
        or len(content) != payload["pdf_size"]
        or sha256(content).hexdigest()
            != payload.get("pdf_sha256")
    ):

        raise ValidationError(
            "Retained certificate PDF fingerprint mismatch."
        )

    try:

        reader = PdfReader(
            BytesIO(content),
            strict=True,
        )

        if (
            reader.is_encrypted
            or len(reader.pages) != 1
            or reader.get_fields()
        ):

            raise ValueError(
                "Unexpected PDF structure."
            )

        extracted = reader.pages[0].extract_text() or ""

    except Exception:

        raise ValidationError(
            "Retained certificate PDF requires review."
        ) from None

    if (
        "FICTIONAL PREVIEW - NOT SIGNED OR AUTHORIZED"
        not in extracted
    ):

        raise ValidationError(
            "Required fictional certificate warning is missing."
        )

    for field in (
        "customer_name",
        "street_address",
        "city",
        "state",
        "zip",
        "project_code",
    ):

        value = identity.get(field)

        if (
            type(value) is not str
            or not value.strip()
            or value not in extracted
        ):

            raise ValidationError(
                "Retained certificate field requires review: "
                + field
            )

    return content


@transaction.atomic
def retain_project_certificate_preview(
    *,
    actor,
    project_id,
    expected_msr_id,
    expected_inspection_id,
    fictional_retention_confirmed,
):

    require_inspection_development_environment()

    if fictional_retention_confirmed is not True:

        raise ValidationError(
            "Confirm fictional certificate preparation."
        )

    prepared = prepare_project_certificate_preview(
        actor=actor,
        project_id=project_id,
    )

    if (
        prepared["msr_id"] != str(expected_msr_id)
        or prepared["inspection_id"]
            != str(expected_inspection_id)
    ):

        raise ValidationError(
            "Approved MSR or inspection changed. "
            "Refresh before preparing the certificate."
        )

    project, msr = _project(
        actor,
        project_id,
    )

    if (
        str(msr.pk) != prepared["msr_id"]
        or canonical_hash(msr.snapshot)
            != prepared["snapshot_sha256"]
    ):

        raise ValidationError(
            "Approved project information changed."
        )

    recipient = approved_recipient(
        msr.snapshot
    )

    if (
        recipient["name"]
        != prepared["identity"]["customer_name"]
    ):

        raise ValidationError(
            "Certificate customer name differs from "
            "the approved customer."
        )

    bindings = {
        "project_id": prepared["project_id"],
        "msr_id": prepared["msr_id"],
        "msr_version": prepared["msr_version"],
        "snapshot_sha256": prepared["snapshot_sha256"],
        "inspection_id": prepared["inspection_id"],
        "inspection_digest": prepared["inspection_digest"],
        "manifest_sha256": prepared["manifest_sha256"],
        "reference_sha256": prepared["reference_sha256"],
        "kind": prepared["kind"],
        "identity": prepared["identity"],
        "recipient": recipient,
    }

    records = list(
        ProjectEvidence.objects
        .select_for_update()
        .filter(
            msr=msr,
            kind=CERTIFICATE_EVIDENCE_KIND,
        )[:2]
    )

    if len(records) > 1:

        raise ValidationError(
            "Conflicting retained certificates require review."
        )

    if records:

        record = records[0]

        validate_retained_certificate(
            payload=record.data,
            digest=record.digest,
        )

        if (
            record.data.get("prepared_by")
                != str(record.created_by_id)
            or any(
                record.data.get(key) != value
                for key, value in bindings.items()
            )
        ):

            raise ValidationError(
                "Retained certificate no longer matches "
                "the approved project and inspection."
            )

        return record, False

    content = prepared["pdf_bytes"]

    if (
        type(content) is not bytes
        or len(content) > MAX_PDF_BYTES
        or sha256(content).hexdigest()
            != prepared["pdf_sha256"]
    ):

        raise ValidationError(
            "Prepared certificate PDF failed integrity checks."
        )

    payload = {
        **bindings,
        "purpose": (
            "FICTIONAL_COMPLETION_CERTIFICATE_PREPARATION"
        ),
        "status": "PREPARED_NOT_AUTHORIZED",
        "prepared_by": str(actor.pk),
        "prepared_at": timezone.now().isoformat(),
        "pdf_base64": b64encode(content).decode("ascii"),
        "pdf_sha256": prepared["pdf_sha256"],
        "pdf_size": len(content),
        "fictional_preview": True,
        **{
            field: False
            for field in FALSE_AUTHORITY_FIELDS
        },
    }

    digest = canonical_hash(payload)

    validate_retained_certificate(
        payload=payload,
        digest=digest,
    )

    record = ProjectEvidence.objects.create(
        msr=msr,
        kind=CERTIFICATE_EVIDENCE_KIND,
        created_by=actor,
        data=payload,
        digest=digest,
    )

    audit(
        actor,
        "installation.fictional_certificate_prepared",
        project.pk,
        {
            "evidence_id": str(record.pk),
            "msr_id": str(msr.pk),
            "inspection_id": prepared["inspection_id"],
            "pdf_sha256": prepared["pdf_sha256"],
            "digest": digest,
            "recipient_status": recipient["status"],
            "fictional_preview": True,
            "recipient_authorized": False,
            "certificate_send_authorized": False,
        },
    )

    return record, True


def require_certificate_recipient_authorization(payload):

    """Fail closed until separate signing authorization is integrated."""

    raise ValidationError(
        "A separately authorized signing recipient is required. "
        "Certificate transmission is not available."
    )
