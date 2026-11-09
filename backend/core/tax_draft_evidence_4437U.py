"""Unregistered tax-draft evidence snapshot; no database writes."""
from copy import deepcopy
import hashlib
import json
from rest_framework.exceptions import ValidationError
from .tax_msr_evidence_4437S import bind_project_tax_draft

def _digest(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def prepare_tax_evidence_package(actor, draft):
    bound = bind_project_tax_draft(actor, draft)
    if bound.get("status") != "DRAFT_VALIDATED_ONLY":
        raise ValidationError("Only a validated draft may be packaged.")
    payload = deepcopy(bound)
    payload["msr_evidence_source"] = "CURRENT_APPROVED_MSR_SNAPSHOT"
    package = {
        "schema": "VERIDIAN_TAX_DRAFT_EVIDENCE_4437U_V1",
        "status": "UNVERIFIED_DRAFT_EVIDENCE_ONLY",
        "prepared_by": bound["prepared_by"],
        "project_id": bound["project_id"],
        "msr_id": bound["approved_msr_id"],
        "msr_version": bound["approved_msr_version"],
        "msr_snapshot_sha256": bound["msr_snapshot_sha256"],
        "source_reference": bound["source_reference"],
        "supporting_document_reference": bound["evidence_reference"],
        "document_authenticity_verified": False,
        "independent_tax_entry_verified": False,
        "accounting_reconciled": False,
        "financial_report_eligible": False,
        "tax_posting_authorized": False,
        "tax_filing_authorized": False,
        "tax_payment_authorized": False,
        "delivery_address_source": (
            "UNVERIFIED_IF_SUPPLIED"
            if payload.get("delivery_address")
            else "NOT_PROVIDED"
        ),
        "captured_draft": payload,
    }
    return {"payload": package, "sha256": _digest(package)}

def evidence_package_digest_matches(candidate):
    if type(candidate) is not dict or set(candidate) != {"payload", "sha256"}:
        return False
    try:
        return type(candidate["sha256"]) is str and _digest(candidate["payload"]) == candidate["sha256"]
    except (TypeError, ValueError, OverflowError):
        return False
