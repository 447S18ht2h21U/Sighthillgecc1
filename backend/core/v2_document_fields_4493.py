"""Seven-document customer/MSR data contract.

Pure preparation only. Never authorizes sending, signing, payment,
installation, statutory waiver, or project completion.
"""
from copy import deepcopy

from .v2_document_mapping_4489 import (
    DOCUMENT_STAGES,
    project_document_projection_v2,
)

COMMON = ("customer_name", "project_code")

ADDRESS = (
    "project_address", "project_city",
    "project_state", "project_zip",
)

CONTACT = ("customer_phone", "customer_email")

# These are the shared MSR values relevant to each reference layout.
# Actual PDF placement must be independently verified.
DOCUMENT_FIELDS = {
    "CUSTOMER_SOW": COMMON + ADDRESS + CONTACT,
    "AGREEMENT": COMMON + ADDRESS,
    "INVOICE": COMMON + ADDRESS + CONTACT,
    "EXPEDITED_SERVICE": COMMON + ("project_address",),
    "RECEIPT": COMMON + ADDRESS + CONTACT,
    "COMPLETION_FINANCED": COMMON + ADDRESS,
    "COMPLETION_NON_FINANCED": COMMON + ADDRESS,
}

# Stage-specific data is NOT manufactured from the MSR.
# These keys identify separate information/evidence needed later.
SEPARATE_STAGE_DATA = {
    "CUSTOMER_SOW": (
        "customer_date_approval_evidence",
        "customer_signature_evidence",
        "manager_review_evidence",
    ),
    "AGREEMENT": (
        "customer_signature_evidence",
        "gecc_signature_evidence",
    ),
    "INVOICE": (
        "invoice_number",
        "invoice_date",
        "approved_commercial_totals",
    ),
    "EXPEDITED_SERVICE": (
        "requested_installation_date",
        "customer_reason",
        "customer_signature_evidence",
        "installation_manager_decision",
        "comptroller_decision",
        "legal_eligibility_verification",
    ),
    "RECEIPT": (
        "actual_equipment_model_numbers",
        "actual_equipment_serial_numbers",
        "verified_final_financials",
        "receipt_delivery_evidence",
    ),
    "COMPLETION_FINANCED": (
        "verified_completion_evidence",
        "customer_signature_evidence",
        "completed_envelope_evidence",
    ),
    "COMPLETION_NON_FINANCED": (
        "verified_completion_evidence",
        "customer_signature_evidence",
        "completed_envelope_evidence",
    ),
}


def prepare_field_contract(snapshot, kind, project_code, msr_version):
    """Read shared facts only; retain stage-specific requirements as pending."""
    if kind not in DOCUMENT_FIELDS:
        raise ValueError("Unsupported document kind.")

    projection = project_document_projection_v2(
        snapshot, kind, project_code, msr_version
    )

    fields = {
        key: projection[key]
        for key in DOCUMENT_FIELDS[kind]
    }

    return deepcopy({
        "kind": kind,
        "reference": projection["reference"],
        "msr_version": projection["msr_version"],
        "stage": DOCUMENT_STAGES[kind],
        "shared_fields": fields,
        "separate_stage_data_required": SEPARATE_STAGE_DATA[kind],
        "send_authorized": False,
        "signature_verified": False,
        "payment_verified": False,
        "installation_eligible": False,
        "completion_verified": False,
    })