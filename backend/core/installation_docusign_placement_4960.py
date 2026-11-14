"""Extract PDF checkbox geometry for offline DocuSign tab planning.

ReportLab coordinates start at bottom-left; DocuSign positions are
measured from top-left. We derive positions from the actual PDF, not
from separately maintained guessed coordinates.

No provider API request, tab installation, sending, or authentication.
"""
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json

from django.core.exceptions import ValidationError
from pypdf import PdfReader
from pypdf.generic import ContentStream

from .installation_docusign_contract_4959 import (
    UnsignedInstallationSigningContract,
    required_installation_signing_fields,
)
from .installation_attestation_pdf_4942 import (
    SIGNATURE_ANCHOR,
    DATE_ANCHOR,
)
from .installation_inspection_form_4945 import (
    INSPECTION_IDS,
)


@dataclass(frozen=True)
class RadioTabPosition:
    field_id: str
    choice: str
    page_number: int
    x: int
    y: int
    width: int = 9
    height: int = 9


@dataclass(frozen=True)
class OfflineInspectionTabPlan:
    unsigned_pdf_sha256: str
    signing_contract_sha256: str
    radio_positions: tuple[RadioTabPosition, ...]
    signature_anchor: str
    date_signed_anchor: str
    plan_sha256: str
    status: str = "OFFLINE_POSITIONS_NOT_INSTALLED"
    provider_tabs_installed: bool = False
    envelope_created: bool = False
    provider_authenticated: bool = False
    inspection_findings_verified: bool = False
    customer_survey_authenticated: bool = False
    completion_authorized: bool = False


def _extract_checkbox_rows(pdf_bytes):
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        if len(reader.pages) != 1 or reader.is_encrypted:
            raise ValidationError("Expected one unencrypted inspection page.")

        page = reader.pages[0]
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if abs(width - 612) > 0.5 or abs(height - 792) > 0.5:
            raise ValidationError("Unexpected inspection page geometry.")

        operations = ContentStream(
            page.get_contents(), reader
        ).operations
        boxes = []

        for operands, operator in operations:
            if operator != b"re" or len(operands) != 4:
                continue

            x, bottom, box_width, box_height = (
                float(value) for value in operands
            )

            if (
                abs(box_width - 9) < 0.01
                and abs(box_height - 9) < 0.01
                and (
                    abs(x - 426) < 0.01
                    or abs(x - 488) < 0.01
                )
            ):
                boxes.append((round(x), round(bottom, 2)))

        if len(boxes) != 16 or len(set(boxes)) != 16:
            raise ValidationError(
                "Expected exactly eight Yes/No checkbox pairs."
            )

        rows = {}
        for x, bottom in boxes:
            rows.setdefault(bottom, set()).add(x)

        if len(rows) != 8 or any(
            xs != {426, 488} for xs in rows.values()
        ):
            raise ValidationError("Checkbox pairs are misaligned.")

        ordered = sorted(rows, reverse=True)

        # The approved layout has the five manager questions in
        # the upper group and three optional survey rows beneath.
        if any(
            ordered[i] - ordered[i + 1] < 15
            for i in range(7)
        ):
            raise ValidationError("Checkbox rows overlap.")

        if ordered[4] - ordered[5] < 35:
            raise ValidationError(
                "Inspection and customer survey groups overlap."
            )

        return height, ordered

    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(
            "Cannot establish trusted PDF checkbox geometry."
        ) from exc


def build_offline_inspection_tab_plan(*, contract, pdf_bytes):
    if type(contract) is not UnsignedInstallationSigningContract:
        raise ValidationError("Signed contract specification required.")
    if type(pdf_bytes) is not bytes:
        raise ValidationError("Unsigned PDF bytes required.")

    if (
        sha256(pdf_bytes).hexdigest()
        != contract.unsigned_pdf_sha256
        or contract.provider != "DOCUSIGN"
        or contract.status != "OFFLINE_SIGNING_CONTRACT_NOT_SENT"
        or contract.envelope_id is not None
        or contract.provider_tabs_installed is not False
        or contract.provider_signature_verified is not False
        or contract.inspection_findings_verified is not False
        or contract.project_completion_authorized is not False
    ):
        raise ValidationError("Untrusted signing contract or PDF mismatch.")

    if contract.fields != required_installation_signing_fields():
        raise ValidationError("Required signing fields changed.")

    if (
        SIGNATURE_ANCHOR.encode() not in pdf_bytes
        or DATE_ANCHOR.encode() not in pdf_bytes
    ):
        raise ValidationError("Signature/date anchors missing.")

    page_height, rows = _extract_checkbox_rows(pdf_bytes)

    radios = []
    for index, field_id in enumerate(INSPECTION_IDS):
        # Only the TOP five rows belong to the Installation Manager.
        # The bottom three survey rows receive NO manager tabs.
        pdf_bottom = rows[index]
        top = round(page_height - (pdf_bottom + 9))

        for answer, x in (("YES", 426), ("NO", 488)):
            radios.append(
                RadioTabPosition(
                    field_id=field_id,
                    choice=answer,
                    page_number=1,
                    x=x,
                    y=top,
                )
            )

    if len(radios) != 10 or len(
        {(item.field_id, item.choice) for item in radios}
    ) != 10:
        raise ValidationError("Invalid manager radio tab positions.")

    payload = {
        "schema": "GECC_OFFLINE_IM_TAB_POSITIONS_4960_V1",
        "contract": contract.contract_sha256,
        "pdf": contract.unsigned_pdf_sha256,
        "radio_positions": [
            vars(position) for position in radios
        ],
        "signature_anchor": SIGNATURE_ANCHOR,
        "date_anchor": DATE_ANCHOR,
    }
    digest = sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()

    return OfflineInspectionTabPlan(
        unsigned_pdf_sha256=contract.unsigned_pdf_sha256,
        signing_contract_sha256=contract.contract_sha256,
        radio_positions=tuple(radios),
        signature_anchor=SIGNATURE_ANCHOR,
        date_signed_anchor=DATE_ANCHOR,
        plan_sha256=digest,
    )
