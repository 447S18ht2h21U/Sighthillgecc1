"""Prepare unsigned fictional Completion Certificate previews.

Use only the approved MSR and validated inspection evidence.
Preserve approved certificate originals.
No signature, payment, release or completion authority is granted.
"""

import re

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import fitz

from pypdf import PdfReader

from django.db import transaction

from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from .documents import canonical_hash

from .models import (
    ProjectEvidence,
    InstallationSchedule,
    User,
    Role,
)

from .distributor_invoice_services_5999 import _project

from .installation_inspection_api_6040 import (
    _fictional_project_allowed,
    _saved_inspection,
    _workspace,
)

from .installation_inspection_transaction_6039 import (
    INSPECTION_KIND,
    require_inspection_development_environment,
)

from .v2_document_mapping_4489 import (
    reference_details,
    project_document_projection_v2,
)


REFERENCE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "docs/reference/GECC-20261107-final-seven"
)

CLASSIFICATIONS = {
    "FINANCED": "COMPLETION_FINANCED",
    "NON_FINANCED": "COMPLETION_NON_FINANCED",
}

ZIP_PATTERN = r"[0-9]{5}(?:-[0-9]{4})?"

FULL_ADDRESS = re.compile(
    r"(?P<street>.+?),\s*"
    r"(?P<city>[^,]+),\s*"
    r"(?P<state>[A-Za-z]{2})\s+"
    r"(?P<zip>" + ZIP_PATTERN + r")"
)

# Coordinates measured from the fingerprint-verified
# November 7 approved reference PDFs.
#
# PyMuPDF uses a top-left origin.
#
# Each entry contains the bounds of the original
# underscore blank, not the adjacent printed label.

FIELD_BOUNDS = {
    "COMPLETION_FINANCED": {
        "customer_name": (
            109.04, 655.74, 246.58, 666.64
        ),
        "street_address": (
            71.98, 688.49, 249.47, 699.40
        ),
        "city": (
            283.58, 688.49, 409.78, 699.40
        ),
        "state": (
            450.47, 688.49, 484.74, 699.40
        ),
        "zip": (
            515.60, 688.49, 567.22, 699.40
        ),
        "project_code": (
            96.55, 721.37, 205.25, 732.28
        ),
    },
    "COMPLETION_NON_FINANCED": {
        "customer_name": (
            109.04, 458.78, 223.50, 469.69
        ),
        "street_address": (
            71.98, 513.51, 226.65, 524.41
        ),
        "city": (
            260.76, 513.51, 386.77, 524.41
        ),
        "state": (
            427.35, 513.51, 461.83, 524.41
        ),
        "zip": (
            492.69, 513.51, 544.20, 524.41
        ),
        "project_code": (
            96.60, 557.30, 205.30, 568.21
        ),
    },
}


def select_completion_certificate(snapshot):

    if type(snapshot) is not dict:

        raise ValidationError(
            "Approved MSR information is required."
        )

    financing = snapshot.get("financing_type")

    if (
        type(financing) is not str
        or financing not in CLASSIFICATIONS
    ):

        raise ValidationError(
            "Approved financing classification is "
            "missing or invalid."
        )

    kind = CLASSIFICATIONS[financing]

    reference_details(kind)

    return kind


def _required_text(value, field):

    if type(value) is not str or not value.strip():

        raise ValidationError(
            "Missing approved certificate field: " + field
        )

    value = value.strip()

    if (
        len(value) > 250
        or any(
            ord(character) < 32
            or ord(character) > 126
            for character in value
        )
    ):

        raise ValidationError(
            "Certificate field requires review: " + field
        )

    return value


def _optional_text(value, field):

    if type(value) is not str:

        raise ValidationError(
            "Invalid approved address field: " + field
        )

    if not value.strip():

        return ""

    return _required_text(value, field)


def _comparison(value):

    return " ".join(value.casefold().split())


def approved_installation_address(snapshot):

    if type(snapshot) is not dict:

        raise ValidationError(
            "Approved installation address is required."
        )

    location = _required_text(
        snapshot.get("project_location"),
        "project_location",
    )

    explicit = {
        field: _optional_text(
            snapshot.get("project_" + field, ""),
            field,
        )
        for field in ("city", "state", "zip")
    }

    match = FULL_ADDRESS.fullmatch(location)

    if match:

        parsed = {
            key: value.strip()
            for key, value in match.groupdict().items()
        }

        for field in ("city", "state", "zip"):

            if (
                explicit[field]
                and _comparison(explicit[field])
                    != _comparison(parsed[field])
            ):

                raise ValidationError(
                    "Conflicting approved installation "
                    "address field: " + field
                )

        street = parsed["street"]

        values = {
            field: explicit[field] or parsed[field]
            for field in ("city", "state", "zip")
        }

    else:

        # A street-only location is accepted only when
        # all separate approved address fields exist.
        # Ambiguous comma-separated addresses must be
        # reviewed rather than guessed.

        if "," in location:

            raise ValidationError(
                "Approved installation address requires review."
            )

        if re.search(
            r"\b[A-Za-z]{2}\s+" + ZIP_PATTERN + r"$",
            location,
        ):

            raise ValidationError(
                "Installation address components are ambiguous."
            )

        street = location

        values = explicit.copy()

    if re.fullmatch(
        r"[A-Za-z]{2}",
        values["state"],
    ) is None:

        raise ValidationError(
            "Approved installation state requires review."
        )

    if re.fullmatch(
        ZIP_PATTERN,
        values["zip"],
    ) is None:

        raise ValidationError(
            "Approved installation ZIP code requires review."
        )

    return {
        "street_address": _required_text(
            street,
            "street_address",
        ),
        "city": _required_text(
            values["city"],
            "city",
        ),
        "state": values["state"].upper(),
        "zip": values["zip"],
    }


def certificate_identity(
    snapshot,
    project_code,
    msr_version,
):

    kind = select_completion_certificate(snapshot)

    projection = project_document_projection_v2(
        snapshot,
        kind,
        project_code,
        str(msr_version),
    )

    result = {
        "customer_name": _required_text(
            projection["customer_name"],
            "customer_name",
        ),
        **approved_installation_address(snapshot),
        "project_code": _required_text(
            projection["project_code"],
            "project_code",
        ),
    }

    return result


def verified_reference_bytes(kind):

    if kind not in FIELD_BOUNDS:

        raise ValidationError(
            "Unsupported Completion Certificate type."
        )

    details = reference_details(kind)

    path = REFERENCE_ROOT / details["filename"]

    if path.is_symlink() or not path.is_file():

        raise ValidationError(
            "Approved Completion Certificate unavailable."
        )

    content = path.read_bytes()

    if (
        sha256(content).hexdigest().upper()
        != details["sha256"]
    ):

        raise ValidationError(
            "Approved certificate fingerprint mismatch."
        )

    reader = PdfReader(
        BytesIO(content),
        strict=True,
    )

    if (
        reader.is_encrypted
        or len(reader.pages) != 1
        or reader.get_fields()
    ):

        raise ValidationError(
            "Unexpected approved certificate structure."
        )

    return content


def _verify_blank(page, bounds):

    matches = []

    for word in page.get_text("words"):

        coordinates = word[:4]

        text = word[4]

        if (
            len(text) >= 3
            and set(text) == {"_"}
            and all(
                abs(actual - expected) <= 0.15
                for actual, expected in zip(
                    coordinates,
                    bounds,
                )
            )
        ):

            matches.append(word)

    if len(matches) != 1:

        raise ValidationError(
            "Approved certificate blank position changed."
        )


def render_fictional_certificate_preview(
    *,
    snapshot,
    project_code,
    msr_version,
    fictional_preview,
):

    require_inspection_development_environment()

    if fictional_preview is not True:

        raise PermissionDenied(
            "Explicit fictional certificate preview required."
        )

    kind = select_completion_certificate(snapshot)

    identity = certificate_identity(
        snapshot,
        project_code,
        msr_version,
    )

    reference = verified_reference_bytes(kind)

    reference_hash = sha256(reference).hexdigest()

    placements = []

    with fitz.open(
        stream=reference,
        filetype="pdf",
    ) as document:

        page = document[0]

        if (
            round(page.rect.width),
            round(page.rect.height),
        ) != (612, 792):

            raise ValidationError(
                "Unexpected certificate page dimensions."
            )

        for field, bounds in FIELD_BOUNDS[kind].items():

            _verify_blank(page, bounds)

            x0, y0, x1, y1 = bounds

            value = identity[field]

            size = 9.0

            while (
                size >= 7.0
                and fitz.get_text_length(
                    value,
                    fontname="helv",
                    fontsize=size,
                ) > x1 - x0 - 4
            ):

                size -= 0.25

            if size < 7.0:

                raise ValidationError(
                    "Certificate field requires layout review: "
                    + field
                )

            placements.append({
                "field": field,
                "value": value,
                "x": x0 + 2,
                "y": y1 - 3,
                "font_size": size,
                "bounds": bounds,
            })

        for item in placements:

            page.insert_text(
                fitz.Point(
                    item["x"],
                    item["y"],
                ),
                item["value"],
                fontsize=item["font_size"],
                fontname="helv",
                color=(0, 0, 0),
                overlay=True,
            )

        warning = (
            "FICTIONAL PREVIEW - NOT SIGNED OR AUTHORIZED"
        )

        width = fitz.get_text_length(
            warning,
            fontname="hebo",
            fontsize=8,
        )

        page.insert_text(
            fitz.Point(
                (page.rect.width - width) / 2,
                16,
            ),
            warning,
            fontsize=8,
            fontname="hebo",
            color=(0.65, 0.10, 0.10),
            overlay=True,
        )

        document.set_metadata({
            "title": (
                "VERIDIAN fictional Completion Certificate"
            ),
            "subject": (
                "Unsigned development preview; "
                "not authorized for delivery"
            ),
        })

        content = document.tobytes(
            garbage=3,
            deflate=True,
        )

    reader = PdfReader(
        BytesIO(content),
        strict=True,
    )

    if (
        len(reader.pages) != 1
        or reader.get_fields()
    ):

        raise ValidationError(
            "Prepared certificate structure is invalid."
        )

    extracted = reader.pages[0].extract_text() or ""

    for field, value in identity.items():

        if value not in extracted:

            raise ValidationError(
                "Prepared certificate field missing: " + field
            )

    if (
        "FICTIONAL PREVIEW" not in extracted
        or "Customer Signature:" not in extracted
    ):

        raise ValidationError(
            "Prepared certificate verification failed."
        )

    # Confirm that each inserted value is present
    # in its own approved field rectangle.

    with fitz.open(
        stream=content,
        filetype="pdf",
    ) as document:

        page = document[0]

        for item in placements:

            x0, y0, x1, y1 = item["bounds"]

            candidates = page.search_for(
                item["value"]
            )

            if not any(
                rectangle.x0 >= x0
                and rectangle.x1 <= x1
                and rectangle.y0 >= y0 - 5
                and rectangle.y1 <= y1 + 2
                for rectangle in candidates
            ):

                raise ValidationError(
                    "Prepared certificate field positioning "
                    "could not be verified: "
                    + item["field"]
                )

    if (
        sha256(
            verified_reference_bytes(kind)
        ).hexdigest() != reference_hash
    ):

        raise ValidationError(
            "Approved certificate original changed."
        )

    return {
        "kind": kind,
        "identity": identity,
        "reference_sha256": reference_hash,
        "pdf_sha256": sha256(content).hexdigest(),
        "pdf_bytes": content,
        "placements": placements,
        "fictional_preview": True,
        "signed": False,
        "send_authorized": False,
        "completion_authorized": False,
    }


@transaction.atomic
def prepare_project_certificate_preview(
    *,
    actor,
    project_id,
):

    require_inspection_development_environment()

    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "pk", None)
    ):

        raise PermissionDenied(
            "Authenticated Installation Manager required."
        )

    current = User.objects.select_for_update().filter(
        pk=actor.pk,
        role=Role.INSTALLATION_MANAGER,
        is_active=True,
    ).first()

    if current is None:

        raise PermissionDenied(
            "Active Installation Manager required."
        )

    project, msr = _project(
        current,
        project_id,
    )

    if not _fictional_project_allowed(project):

        raise PermissionDenied(
            "Only the designated fictional project "
            "may use this certificate preview."
        )

    saved = _saved_inspection(
        project,
        msr,
    )

    if (
        saved is None
        or saved["status"]
            != "INTERNAL_ACCEPTANCE_CANDIDATE"
        or saved["fictional_acceptance_test"] is not True
    ):

        raise ValidationError(
            "Saved fictional installation acceptance required."
        )

    record = ProjectEvidence.objects.select_for_update().get(
        pk=saved["inspection_id"],
        msr=msr,
        kind=INSPECTION_KIND,
    )

    if (
        record.created_by_id != current.pk
        or record.data["all_equipment_confirmed"] is not True
        or record.digest != canonical_hash(record.data)
    ):

        raise ValidationError(
            "Saved inspection evidence requires review."
        )

    schedules = list(
        InstallationSchedule.objects.select_for_update().filter(
            pk=record.data["schedule_id"],
            project=project,
            installation_manager=current,
            status=InstallationSchedule.Status.COMPLETED,
        )[:2]
    )

    if len(schedules) != 1:

        raise ValidationError(
            "Completed installation assignment requires review."
        )

    workspace = _workspace(
        project,
        msr,
    )

    if (
        workspace["manifest_sha256"]
            != record.data["manifest_sha256"]
        or workspace["snapshot_sha256"]
            != record.data["snapshot_sha256"]
        or workspace["equipment_manifest"][
            "distributor_purchase_review_complete"
        ] is not True
    ):

        raise ValidationError(
            "Approved project or purchasing evidence "
            "changed after inspection."
        )

    findings = saved["findings"]

    required = (
        "equipment_and_serial_numbers_confirmed",
        "required_materials_confirmed",
        "distributor_invoice_uploaded_and_verified",
        "personally_inspected",
        "scope_completed_professionally",
        "technician_delivered_quality_service",
        "job_site_clean",
    )

    if not all(
        findings.get(field) is True
        for field in required
    ):

        raise ValidationError(
            "Required inspection confirmations are incomplete."
        )

    if (
        findings.get("decision") != "ACCEPT"
        or findings.get("customer_impression")
            != "SATISFIED"
    ):

        raise ValidationError(
            "Inspection findings require resolution."
        )

    result = render_fictional_certificate_preview(
        snapshot=msr.snapshot,
        project_code=project.code,
        msr_version=msr.number,
        fictional_preview=True,
    )

    result.update({
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "inspection_id": str(record.pk),
        "inspection_digest": record.digest,
        "manifest_sha256": record.data["manifest_sha256"],
        "inspection_findings": deepcopy(findings),
        "equipment_unit_count": len(saved["equipment"]),
        "prepared_by": str(current.pk),
        "trusted_installation_evidence": False,
        "installation_acceptance_authorized": False,
        "customer_document_release_authorized": False,
        "certificate_send_authorized": False,
    })

    return result
