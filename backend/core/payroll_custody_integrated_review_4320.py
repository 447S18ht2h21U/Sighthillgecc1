"""Test-only intersection of payroll evidence and custody comparisons.

Requires all existing candidate safeguards but never authenticates a
custodian, approves an earning date, permits payroll visibility,
or enables operational services. No network or writes.
"""
from .payroll_checkpoint_antirollback_4314 import (
    candidate_antirollback_payroll_evidence,
)
from .payroll_external_custody_boundary_4319 import (
    candidate_custody_manifest,
    candidate_custody_receipt_comparison,
)


def candidate_integrated_custody_review(
    *, payment_id, checkpoint, registry,
    expected_issuer, trusted_minimum, receipt
):
    manifest = candidate_custody_manifest()
    if manifest is None:
        return None

    if type(checkpoint) is not dict:
        return None

    # This candidate is deliberately bound to the CURRENT verified
    # audit head, not merely a valid earlier historical checkpoint.
    if (
        type(checkpoint.get("sequence")) is not int
        or checkpoint["sequence"] != manifest["audit_sequence"]
        or checkpoint.get("digest") != manifest["audit_digest"]
    ):
        return None

    comparison = candidate_custody_receipt_comparison(
        manifest=manifest,
        receipt=receipt,
    )
    if comparison is None:
        return None

    if (
        comparison.get("external_custodian_authenticated") is not False
        or comparison.get("durable_external_storage_verified") is not False
        or comparison.get("earning_date_authorized") is not False
        or comparison.get("payroll_access_authorized") is not False
    ):
        return None

    evidence = candidate_antirollback_payroll_evidence(
        payment_id=payment_id,
        checkpoint=checkpoint,
        registry=registry,
        expected_issuer=expected_issuer,
        trusted_minimum=trusted_minimum,
    )
    if evidence is None:
        return None

    if evidence.get("earning_date_authorized") is not False:
        return None

    return {
        **evidence,
        "custody_manifest_sha256": manifest["manifest_sha256"],
        "custody_receipt_fields_match": True,
        "external_custodian_authenticated": False,
        "durable_external_storage_verified": False,
        "external_audit_anchor_verified": False,
        "earning_date_authorized": False,
        "payroll_access_authorized": False,
        "review_status": "INTEGRATED_UNTRUSTED_CUSTODY_TEST_ONLY",
    }


def integrated_custody_grants_live_access(*args, **kwargs):
    return False