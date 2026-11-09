"""Test-only custody read-back comparison.

Read-back is passed as untrusted input. Field equality alone cannot
prove independent storage, issuer identity, delivery, or freshness.
Production authentication, durable custody, and real transport are
not implemented. No operational authorization or database writes.
"""
import re

from .payroll_external_custody_boundary_4319 import (
    candidate_custody_manifest,
)
from .payroll_custody_integrated_review_4320 import (
    candidate_integrated_custody_review,
)

_READBACK_FIELDS = frozenset({
    "custodian_id", "manifest", "receipt"
})


def candidate_custody_readback_review(
    *, payment_id, checkpoint, registry, expected_issuer,
    trusted_minimum, receipt, readback, expected_custodian
):
    if (
        type(expected_custodian) is not str
        or re.fullmatch(
            r"[A-Za-z0-9_-]{1,64}", expected_custodian
        ) is None
    ):
        return None

    if (
        type(readback) is not dict
        or set(readback) != _READBACK_FIELDS
        or type(receipt) is not dict
    ):
        return None

    if (
        readback.get("custodian_id") != expected_custodian
        or receipt.get("custodian_id") != expected_custodian
    ):
        return None

    manifest = candidate_custody_manifest()
    if manifest is None:
        return None

    # Require complete copies, not merely a matching digest claim.
    if (
        type(readback.get("manifest")) is not dict
        or readback["manifest"] != manifest
        or type(readback.get("receipt")) is not dict
        or readback["receipt"] != receipt
    ):
        return None

    evidence = candidate_integrated_custody_review(
        payment_id=payment_id,
        checkpoint=checkpoint,
        registry=registry,
        expected_issuer=expected_issuer,
        trusted_minimum=trusted_minimum,
        receipt=receipt,
    )
    if evidence is None:
        return None

    if (
        evidence.get("earning_date_authorized") is not False
        or evidence.get("payroll_access_authorized") is not False
        or evidence.get("external_custodian_authenticated") is not False
    ):
        return None

    return {
        **evidence,
        "test_readback_fields_match": True,
        "test_claimed_custodian": expected_custodian,
        "external_custodian_authenticated": False,
        "durable_external_storage_verified": False,
        "external_audit_anchor_verified": False,
        "earning_date_authorized": False,
        "payroll_access_authorized": False,
        "review_status": "TEST_READBACK_MATCHED_CUSTODY_UNVERIFIED",
    }


def custody_readback_grants_live_access(*args, **kwargs):
    return False