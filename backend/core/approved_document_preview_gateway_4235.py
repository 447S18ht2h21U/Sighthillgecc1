"""Fail-closed development gateway for six approved PDF previews.

This gateway is deliberately NOT an API route, production renderer,
signing provider, approval service, or document-release service.
It accepts only explicitly fictional review data and never persists it.
"""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import os

from pypdf import PdfReader


GATE_VARIABLE = "VERIDIAN_APPROVED_PDF_PREVIEW_GATE"
GATE_VALUE = "enabled-test-only"

DOCUMENT_KINDS = frozenset({
    "CUSTOMER_SOW",
    "AGREEMENT",
    "INVOICE",
    "RECEIPT",
    "COMPLETION_FINANCED",
    "COMPLETION_NON_FINANCED",
})

REQUIRED_DETAILS = {
    "CUSTOMER_SOW": frozenset({
        "project_code", "msr_version", "created", "associate",
    }),
    "AGREEMENT": frozenset({"project_code", "msr_version"}),
    "INVOICE": frozenset({
        "project_code", "invoice_number", "invoice_date",
    }),
    "RECEIPT": frozenset({
        "project_code", "invoice_number", "invoice_date",
    }),
    "COMPLETION_FINANCED": frozenset({"project_code"}),
    "COMPLETION_NON_FINANCED": frozenset({"project_code"}),
}


class PreviewDenied(ValueError):
    """The requested activity is not authorized for development previews."""


def _require_preview_gate():
    if (
        os.environ.get(GATE_VARIABLE) != GATE_VALUE
        or os.environ.get("VERIDIAN_ENVIRONMENT") != "development"
        or os.environ.get("GECC_DEV") != "1"
    ):
        raise PreviewDenied("Approved PDF development gateway is disabled.")


def _validate_request(kind, snapshot, details):
    if kind not in DOCUMENT_KINDS:
        raise PreviewDenied("Unrecognized approved document kind.")
    if type(snapshot) is not dict:
        raise PreviewDenied("MSR preview snapshot must be a dictionary.")
    if type(details) is not dict:
        raise PreviewDenied("Preview details must be a dictionary.")

    customer = snapshot.get("customer")
    if (
        type(customer) is not str
        or "FICTIONAL" not in customer.upper()
    ):
        raise PreviewDenied("Only fictional customer fixtures are permitted.")

    expected = REQUIRED_DETAILS[kind]
    if set(details) != expected:
        raise PreviewDenied("Preview detail contract mismatch.")

    for key, value in details.items():
        if (
            type(value) is not str
            or not value.strip()
            or len(value) > 160
            or any(ord(char) < 32 for char in value)
        ):
            raise PreviewDenied(f"Invalid preview detail: {key}.")

    financing = snapshot.get("financing_type")
    if kind == "COMPLETION_FINANCED" and financing != "FINANCED":
        raise PreviewDenied("Financed certificate requires financed MSR.")
    if kind == "COMPLETION_NON_FINANCED" and financing != "NON_FINANCED":
        raise PreviewDenied("Non-financed certificate requires non-financed MSR.")


def _render_selected(kind, directory, snapshot, details):
    """Dispatch only to previously developed, non-operational renderers."""
    if kind == "CUSTOMER_SOW":
        from .approved_sow_page_two_4232 import create_page_two_sow_preview
        return create_page_two_sow_preview(
            directory, snapshot, details["project_code"],
            details["msr_version"], details["created"], details["associate"],
        )

    if kind == "AGREEMENT":
        from .approved_sow_agreement_previews_4230 import create_agreement_preview
        return create_agreement_preview(
            directory, snapshot, details["project_code"],
            details["msr_version"],
        )

    if kind == "INVOICE":
        from .approved_invoice_commercial_preview_4222 import (
            create_commercial_invoice_preview,
        )
        return create_commercial_invoice_preview(
            directory, snapshot, details["project_code"],
            details["invoice_number"], details["invoice_date"],
        )

    if kind == "RECEIPT":
        from .approved_receipt_overlay_preview_4223 import create_receipt_preview
        return create_receipt_preview(
            directory, snapshot, details["project_code"],
            details["invoice_number"], details["invoice_date"],
        )

    if kind.startswith("COMPLETION_"):
        from .approved_completion_previews_4227 import create_completion_preview
        return create_completion_preview(
            directory, snapshot, details["project_code"], kind,
        )

    raise PreviewDenied("Unsupported document renderer.")


def build_fictional_preview(
    kind, directory, snapshot, details, *,
    review_only=False,
    signing_test=False,
    release_context=None,
):
    """Return verified preview bytes and SHA-256, with no side effects."""
    _require_preview_gate()

    if not review_only or signing_test or release_context is not None:
        raise PreviewDenied(
            "Only isolated, unsigned fictional reviews are permitted."
        )

    _validate_request(kind, snapshot, details)

    directory = Path(directory)
    if not directory.is_dir():
        raise PreviewDenied("Approved reference directory is unavailable.")

    # Caller data must remain untouched, including nested equipment rows.
    original_snapshot = deepcopy(snapshot)
    original_details = deepcopy(details)

    content = _render_selected(
        kind, directory, deepcopy(snapshot), deepcopy(details),
    )

    if type(content) is not bytes or not content.startswith(b"%PDF-"):
        raise PreviewDenied("Renderer did not return PDF bytes.")

    reader = PdfReader(BytesIO(content), strict=True)
    if not reader.pages:
        raise PreviewDenied("Renderer produced an empty PDF.")

    text = "\n".join(
        page.extract_text() or "" for page in reader.pages
    ).upper()

    if "FICTIONAL" not in text:
        raise PreviewDenied("Required fictional preview marking is missing.")

    if snapshot != original_snapshot or details != original_details:
        raise PreviewDenied("Preview source values changed unexpectedly.")

    return {
        "kind": kind,
        "content": content,
        "sha256": sha256(content).hexdigest().upper(),
        "page_count": len(reader.pages),
        "development_only": True,
        "signed": False,
        "released": False,
    }