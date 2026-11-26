"""Development-only customer Completion Certificate signing package.

The sandbox recipient is not an approved operational customer signer.
No provider calls, envelope creation, transmission or financial authority.
"""

import os
import re

from base64 import b64encode
from hashlib import sha256

import fitz

from django.db import transaction
from django.utils import timezone

from rest_framework.exceptions import ValidationError

from .documents import canonical_hash

from .models import ProjectEvidence

from .services import audit

from .completion_certificate_retention_6052 import (
    CERTIFICATE_EVIDENCE_KIND,
    validate_retained_certificate,
    approved_recipient,
)

from .completion_certificate_preparation_6048 import (
    prepare_project_certificate_preview,
    verified_reference_bytes,
)

from .installation_inspection_transaction_6039 import (
    require_inspection_development_environment,
)

from .distributor_invoice_services_5999 import _project


SANDBOX_PACKAGE_KIND = "CERT_SANDBOX_6056"

DESIGNATED_SANDBOX_RECIPIENT = "doug@sighthill.net"

PROJECT_CODE = "101-SA-2026-10-05"

CUSTOMER_NAME = "GECC Test Customer"


SIGNING_BOUNDS = {
    "COMPLETION_FINANCED": {
        "customer_signature": (
            347.37, 655.74, 467.75, 666.64,
        ),
        "customer_signed_date": (
            499.32, 655.74, 567.98, 666.64,
        ),
    },
    "COMPLETION_NON_FINANCED": {
        "customer_signature": (
            324.27, 458.78, 444.83, 469.69,
        ),
        "customer_signed_date": (
            476.41, 458.78, 545.07, 469.69,
        ),
    },
}


def require_designated_sandbox_recipient(email):

    require_inspection_development_environment()

    if (
        type(email) is not str
        or email.strip().casefold()
            != DESIGNATED_SANDBOX_RECIPIENT
    ):

        raise ValidationError(
            "Only the designated fictional certificate "
            "sandbox recipient may be used."
        )

    allowed = {
        item.strip().casefold()
        for item in os.environ.get(
            "GECC_SANDBOX_TEST_EMAILS",
            "",
        ).split(",")
        if item.strip()
    }

    if DESIGNATED_SANDBOX_RECIPIENT not in allowed:

        raise ValidationError(
            "Designated recipient is not in the "
            "configured sandbox allowlist."
        )

    return DESIGNATED_SANDBOX_RECIPIENT


def blank_acknowledgment_bounds(page):

    labels = page.search_for("On this date")

    if len(labels) != 1:

        raise ValidationError(
            "Acknowledgment date label requires review."
        )

    label = labels[0]

    candidates = []

    for word in page.get_text("words"):

        x0, y0, x1, y1, text = word[:5]

        if not re.fullmatch(r"_{3,}", text):

            continue

        if (
            x0 >= label.x1 - 2
            and x0 <= label.x1 + 35
            and abs(
                (y0 + y1) / 2
                - (label.y0 + label.y1) / 2
            ) <= 8
            and x1 - x0 >= 45
        ):

            candidates.append(
                (x0, y0, x1, y1)
            )

    if len(candidates) != 1:

        raise ValidationError(
            "Acknowledgment date blank requires review."
        )

    return tuple(
        round(value, 2)
        for value in candidates[0]
    )


def require_blank(page, bounds):

    for word in page.get_text("words"):

        actual = tuple(word[:4])

        if (
            re.fullmatch(r"_{3,}", word[4])
            and all(
                abs(left - right) <= 0.25
                for left, right in zip(
                    actual,
                    bounds,
                )
            )
        ):

            return

    raise ValidationError(
        "Required signature or date blank is not intact."
    )


def signing_layout(kind, retained_pdf):

    if kind not in SIGNING_BOUNDS:

        raise ValidationError(
            "Unsupported Completion Certificate classification."
        )

    reference = verified_reference_bytes(kind)

    with fitz.open(
        stream=reference,
        filetype="pdf",
    ) as original:

        with fitz.open(
            stream=retained_pdf,
            filetype="pdf",
        ) as retained:

            if len(original) != 1 or len(retained) != 1:

                raise ValidationError(
                    "Expected one-page Completion Certificate."
                )

            original_page = original[0]

            retained_page = retained[0]

            for page in (
                original_page,
                retained_page,
            ):

                if (
                    page.rotation != 0
                    or round(page.rect.width) != 612
                    or round(page.rect.height) != 792
                    or page.cropbox != page.mediabox
                ):

                    raise ValidationError(
                        "Certificate page geometry requires review."
                    )

            bounds = {
                **SIGNING_BOUNDS[kind],
                "acknowledgment_date": (
                    blank_acknowledgment_bounds(
                        original_page
                    )
                ),
            }

            for rectangle in bounds.values():

                require_blank(
                    original_page,
                    rectangle,
                )

                require_blank(
                    retained_page,
                    rectangle,
                )

            retained_text = retained_page.get_text()

            if (
                "FICTIONAL PREVIEW - NOT SIGNED OR AUTHORIZED"
                not in retained_text
            ):

                raise ValidationError(
                    "Fictional certificate warning missing."
                )

    def tab(label, rectangle, *, signature=False):

        x0, y0, x1, y1 = rectangle

        # Candidate top-left placement at 72 DPI.
        # The provider's actual signing-screen rendering
        # must be confirmed before transmission is enabled.

        y = round(y1 - (24 if signature else 13))

        x = round(x0 + 2)

        if (
            x < 0
            or y < 0
            or x >= 612
            or y >= 792
        ):

            raise ValidationError(
                "Signing tab lies outside the certificate."
            )

        return {
            "documentId": "1",
            "recipientId": "1",
            "pageNumber": "1",
            "xPosition": str(x),
            "yPosition": str(y),
            "tabLabel": label,
        }

    signature = tab(
        "customer_signature",
        bounds["customer_signature"],
        signature=True,
    )

    signature.update({
        "optional": "false",
        "scaleValue": "0.65",
    })

    return {
        "bounds": {
            key: list(value)
            for key, value in bounds.items()
        },
        "tabs": {
            "signHereTabs": [
                signature,
            ],
            "dateSignedTabs": [
                tab(
                    "customer_signed_date",
                    bounds["customer_signed_date"],
                ),
                tab(
                    "acknowledgment_date",
                    bounds["acknowledgment_date"],
                ),
            ],
        },
        "provider_layout_verified": False,
    }


@transaction.atomic
def prepare_sandbox_certificate_package(
    *,
    actor,
    project_id,
    expected_certificate_id,
    expected_certificate_digest,
    sandbox_recipient,
    fictional_confirmed,
):

    require_inspection_development_environment()

    if fictional_confirmed is not True:

        raise ValidationError(
            "Explicit fictional signing preparation required."
        )

    email = require_designated_sandbox_recipient(
        sandbox_recipient
    )

    prepared = prepare_project_certificate_preview(
        actor=actor,
        project_id=project_id,
    )

    project, msr = _project(
        actor,
        project_id,
    )

    if (
        project.code != PROJECT_CODE
        or project.customer.legal_name != CUSTOMER_NAME
    ):

        raise ValidationError(
            "This sandbox preparation is restricted "
            "to the designated fictional project."
        )

    records = list(
        ProjectEvidence.objects
        .select_for_update()
        .filter(
            msr=msr,
            kind=CERTIFICATE_EVIDENCE_KIND,
        )[:2]
    )

    if len(records) != 1:

        raise ValidationError(
            "Exactly one retained certificate is required."
        )

    certificate = records[0]

    if (
        str(certificate.pk)
            != str(expected_certificate_id)
        or certificate.digest
            != expected_certificate_digest
    ):

        raise ValidationError(
            "Retained certificate changed. Refresh before proceeding."
        )

    content = validate_retained_certificate(
        payload=certificate.data,
        digest=certificate.digest,
    )

    for field in (
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

        if certificate.data.get(field) != prepared[field]:

            raise ValidationError(
                "Retained certificate no longer matches "
                "the current approved project and inspection."
            )

    if (
        certificate.data.get("prepared_by")
            != str(certificate.created_by_id)
        or certificate.data["recipient"]
            != approved_recipient(msr.snapshot)
    ):

        raise ValidationError(
            "Retained certificate provenance requires review."
        )

    layout = signing_layout(
        certificate.data["kind"],
        content,
    )

    bindings = {
        "purpose": "FICTIONAL_CERTIFICATE_SANDBOX_PACKAGE",
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "snapshot_sha256": prepared["snapshot_sha256"],
        "inspection_id": prepared["inspection_id"],
        "inspection_digest": prepared["inspection_digest"],
        "certificate_id": str(certificate.pk),
        "certificate_digest": certificate.digest,
        "certificate_kind": certificate.data["kind"],
        "pdf_sha256": certificate.data["pdf_sha256"],
        "recipient": {
            "name": CUSTOMER_NAME,
            "email": email,
            "classification": "DESIGNATED_SANDBOX_RECIPIENT",
            "operational_customer_authority": False,
        },
        "layout": layout,
        "fictional": True,
        "status": "SANDBOX_PREPARED_NOT_SENT",
        "signed": False,
        "provider_authenticated": False,
        "provider_layout_verified": False,
        "sandbox_send_authorized": False,
        "certificate_send_authorized": False,
        "operational_customer_authority": False,
        "installation_acceptance_authorized": False,
        "financial_posting_authorized": False,
        "completion_authorized": False,
    }

    records = list(
        ProjectEvidence.objects
        .select_for_update()
        .filter(
            msr=msr,
            kind=SANDBOX_PACKAGE_KIND,
        )[:2]
    )

    if len(records) > 1:

        raise ValidationError(
            "Conflicting sandbox packages require review."
        )

    if records:

        existing = records[0]

        if (
            existing.digest
                != canonical_hash(existing.data)
            or existing.data.get("prepared_by")
                != str(existing.created_by_id)
            or any(
                existing.data.get(key) != value
                for key, value in bindings.items()
            )
        ):

            raise ValidationError(
                "Existing sandbox package requires review."
            )

        return existing, False

    payload = {
        **bindings,
        "prepared_by": str(actor.pk),
        "prepared_at": timezone.now().isoformat(),
    }

    digest = canonical_hash(payload)

    package = ProjectEvidence.objects.create(
        msr=msr,
        kind=SANDBOX_PACKAGE_KIND,
        created_by=actor,
        data=payload,
        digest=digest,
    )

    audit(
        actor,
        "installation.fictional_certificate_sandbox_prepared",
        project.pk,
        {
            "package_id": str(package.pk),
            "package_digest": digest,
            "certificate_id": str(certificate.pk),
            "certificate_digest": certificate.digest,
            "pdf_sha256": bindings["pdf_sha256"],
            "sandbox_recipient": email,
            "fictional": True,
            "sandbox_send_authorized": False,
            "operational_customer_authority": False,
        },
    )

    return package, True


def sandbox_envelope_preview(
    *,
    package,
    certificate,
):

    require_inspection_development_environment()

    if (
        package.kind != SANDBOX_PACKAGE_KIND
        or certificate.kind != CERTIFICATE_EVIDENCE_KIND
        or package.msr_id != certificate.msr_id
        or canonical_hash(package.data) != package.digest
        or package.data.get("certificate_id")
            != str(certificate.pk)
        or package.data.get("certificate_digest")
            != certificate.digest
        or package.data.get("pdf_sha256")
            != certificate.data.get("pdf_sha256")
        or package.data.get("prepared_by")
            != str(package.created_by_id)
        or package.data.get("fictional") is not True
        or package.data.get("status")
            != "SANDBOX_PREPARED_NOT_SENT"
    ):

        raise ValidationError(
            "Sandbox package provenance requires review."
        )

    data = package.data

    for field in (
        "signed",
        "provider_authenticated",
        "provider_layout_verified",
        "sandbox_send_authorized",
        "certificate_send_authorized",
        "operational_customer_authority",
        "installation_acceptance_authorized",
        "financial_posting_authorized",
        "completion_authorized",
    ):

        if data.get(field) is not False:

            raise ValidationError(
                "Unexpected sandbox authorization state."
            )

    msr = package.msr

    if (
        msr.status != "APPROVED"
        or msr.project.current_approved_id != msr.pk
        or msr.project.code != PROJECT_CODE
        or msr.project.customer.legal_name != CUSTOMER_NAME
        or msr.project.state == "CANCELLED"
        or data.get("snapshot_sha256")
            != canonical_hash(msr.snapshot)
    ):

        raise ValidationError(
            "Current fictional approved MSR required."
        )

    content = validate_retained_certificate(
        payload=certificate.data,
        digest=certificate.digest,
    )

    email = require_designated_sandbox_recipient(
        data["recipient"]["email"]
    )

    if data["recipient"] != {
        "name": CUSTOMER_NAME,
        "email": email,
        "classification": "DESIGNATED_SANDBOX_RECIPIENT",
        "operational_customer_authority": False,
    }:

        raise ValidationError(
            "Unexpected fictional recipient classification."
        )

    layout = signing_layout(
        certificate.data["kind"],
        content,
    )

    if data.get("layout") != layout:

        raise ValidationError(
            "Stored signing layout requires review."
        )

    # Metadata and exact document bytes only.
    # This is not a provider request and must not be sent.

    return {
        "status": "created",
        "emailSubject": (
            "FICTIONAL TEST - GECC Completion Certificate"
        ),
        "emailBlurb": (
            "Sandbox test only. No actual customer acceptance, "
            "funding release or payment authorization."
        ),
        "documents": [
            {
                "documentId": "1",
                "name": (
                    "FICTIONAL GECC Completion Certificate.pdf"
                ),
                "fileExtension": "pdf",
                "documentBase64": (
                    b64encode(content).decode("ascii")
                ),
                "transformPdfFields": "false",
            }
        ],
        "recipients": {
            "signers": [
                {
                    "recipientId": "1",
                    "routingOrder": "1",
                    "name": CUSTOMER_NAME,
                    "email": email,
                    "tabs": layout["tabs"],
                }
            ]
        },
        "notification": {
            "useAccountDefaults": "false",
            "expirations": {
                "expireEnabled": "true",
                "expireAfter": "75",
                "expireWarn": "5",
            },
        },
    }
