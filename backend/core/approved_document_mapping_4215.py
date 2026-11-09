"""Approved November 3 document-reference mapping.

Pure data projection only. No database, PDF writes, document release,
signature, payment verification, or operational route activation.

The six approved original PDFs must be retained separately and
matched by their exact content fingerprints before deployment.
"""
from copy import deepcopy

from .msr_document_source import customer_document_data
from .equipment_invoice_rows import project_equipment_rows


APPROVED_REFERENCE_FILES = {
    "CUSTOMER_SOW": "GECC Project Scope of Work ref1103a.pdf",
    "AGREEMENT": "GECC Project  Agreement ref1103MD.pdf",
    "INVOICE": "GECC Invoice ref1103.pdf",
    "RECEIPT": "GECC Receipt ref1103.pdf",
    "COMPLETION_NON_FINANCED": "Completion Certificate ref1103NF.pdf",
    "COMPLETION_FINANCED": "Completion Certificate ref1103F.pdf",
}

COMMON_FIELDS = (
    "customer",
    "billing_address",
    "project_location",
    "project_city",
    "project_state",
    "project_zip",
    "customer_phone",
    "customer_email",
)

EQUIPMENT_DOCUMENTS = frozenset({
    "CUSTOMER_SOW",
    "INVOICE",
    "RECEIPT",
})


def approved_reference_filename(kind):
    """Identify the exact approved reference filename; no fuzzy matching."""
    if kind not in APPROVED_REFERENCE_FILES:
        raise ValueError("Unsupported approved document reference.")
    return APPROVED_REFERENCE_FILES[kind]


def project_document_projection(snapshot, kind):
    """Project approved shared MSR values without modifying their source.

    Invoice-specific prices and installation-stage serial numbers are
    deliberately excluded. They require separately controlled processing.
    """
    filename = approved_reference_filename(kind)
    common = customer_document_data(snapshot)

    if not common["customer"].strip():
        raise ValueError("MSR customer name is required.")

    result = {
        "reference_kind": kind,
        "reference_filename": filename,
        "customer_name": common["customer"],
        "billing_address": common["billing_address"],
        "project_address": common["project_location"],
        "project_city": common["project_city"],
        "project_state": common["project_state"],
        "project_zip": common["project_zip"],
        "customer_phone": common["customer_phone"],
        "customer_email": common["customer_email"],
    }

    if kind in EQUIPMENT_DOCUMENTS:
        result["equipment_rows"] = project_equipment_rows(snapshot)

    return deepcopy(result)