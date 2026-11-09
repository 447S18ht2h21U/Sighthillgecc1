"""Six-document fictional integration, deliberately not an operational path.

Uses the already-gated preview gateway. No ORM, file writes, API routes,
approval evidence, electronic signatures, delivery or production access.
"""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO

from pypdf import PdfReader

from .approved_document_preview_gateway_4235 import (
    build_fictional_preview, PreviewDenied,
)

KINDS = (
    "CUSTOMER_SOW",
    "AGREEMENT",
    "INVOICE",
    "RECEIPT",
    "COMPLETION_NON_FINANCED",
    "COMPLETION_FINANCED",
)


def build_six_document_review(directory, snapshot, *, project_code,
                              msr_version, created, associate,
                              invoice_number, invoice_date):
    """Return six verified in-memory PDFs and a review-only manifest."""
    if type(snapshot) is not dict:
        raise PreviewDenied("A fictional MSR snapshot is required.")
    if snapshot.get("financing_type") not in ("FINANCED", "NON_FINANCED"):
        raise PreviewDenied("Explicit financing classification is required.")

    initial = deepcopy(snapshot)
    common = {
        "project_code": project_code,
    }
    details = {
        "CUSTOMER_SOW": {
            **common, "msr_version": msr_version,
            "created": created, "associate": associate,
        },
        "AGREEMENT": {
            **common, "msr_version": msr_version,
        },
        "INVOICE": {
            **common, "invoice_number": invoice_number,
            "invoice_date": invoice_date,
        },
        "RECEIPT": {
            **common, "invoice_number": invoice_number,
            "invoice_date": invoice_date,
        },
        "COMPLETION_NON_FINANCED": common,
        "COMPLETION_FINANCED": common,
    }

    results = {}
    manifest = []
    customer = snapshot.get("customer", "")
    if type(customer) is not str or not customer.strip():
        raise PreviewDenied("A fictional customer name is required.")

    for kind in KINDS:
        working = deepcopy(snapshot)
        if kind == "COMPLETION_FINANCED":
            working["financing_type"] = "FINANCED"
        elif kind == "COMPLETION_NON_FINANCED":
            working["financing_type"] = "NON_FINANCED"

        item = build_fictional_preview(
            kind, directory, working, deepcopy(details[kind]),
            review_only=True,
        )

        content = item["content"]
        text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(BytesIO(content), strict=True).pages
        )
        if customer not in text or project_code not in text:
            raise PreviewDenied(
                f"MSR customer/project mismatch in {kind} preview."
            )
        if not item["development_only"] or item["signed"] or item["released"]:
            raise PreviewDenied("Operational or signing state was introduced.")
        if item["sha256"] != sha256(content).hexdigest().upper():
            raise PreviewDenied("PDF fingerprint mismatch.")

        results[kind] = content
        manifest.append({
            "kind": kind,
            "pages": item["page_count"],
            "sha256": item["sha256"],
            "status": "FICTIONAL_REVIEW_ONLY",
        })

    if snapshot != initial or len(manifest) != 6:
        raise PreviewDenied("Source changed or preview batch incomplete.")

    return {
        "manifest": tuple(manifest),
        "pdfs": results,
        "signed": False,
        "released": False,
        "customer_delivery": False,
    }