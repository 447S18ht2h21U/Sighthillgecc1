"""Test-only HMAC signature checks for supplied audit checkpoints.

An HMAC proves possession of the supplied verification key; it cannot
prove the checkpoint came from an independent, trusted custodian.
Key management, source authentication, secure offsite anchoring,
rotation, and anti-rollback protections are NOT implemented.

Never register this module for live payroll or financial authorization.
"""
import hashlib
import hmac
import json
import re

from .payroll_technical_provenance_4296 import _uuid
from .payroll_audit_checkpoint_4311 import (
    candidate_checkpoint_checked_payroll_evidence,
)

_SCHEMA = "VERIDIAN_TEST_AUDIT_CHECKPOINT_V1"
_FIELDS = frozenset({
    "schema", "key_id", "sequence", "digest", "signature",
})


def _canonical_checkpoint_bytes(checkpoint):
    return json.dumps(
        {
            "schema": checkpoint["schema"],
            "key_id": checkpoint["key_id"],
            "sequence": checkpoint["sequence"],
            "digest": checkpoint["digest"],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def candidate_signed_checkpoint_matches(
    *, checkpoint, verification_key
):
    if type(checkpoint) is not dict:
        return False
    if set(checkpoint) != _FIELDS:
        return False

    if (
        checkpoint.get("schema") != _SCHEMA
        or type(checkpoint.get("key_id")) is not str
        or re.fullmatch(
            r"[A-Za-z0-9_-]{1,64}", checkpoint["key_id"]
        ) is None
    ):
        return False

    sequence = checkpoint.get("sequence")
    digest = checkpoint.get("digest")
    signature = checkpoint.get("signature")

    if type(sequence) is not int or sequence < 1:
        return False
    if (
        type(digest) is not str
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
    ):
        return False
    if (
        type(signature) is not str
        or re.fullmatch(r"[0-9a-f]{64}", signature) is None
    ):
        return False

    if (
        type(verification_key) is not bytes
        or len(verification_key) < 32
    ):
        return False

    expected = hmac.new(
        verification_key,
        _canonical_checkpoint_bytes(checkpoint),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


def candidate_signed_checkpoint_payroll_evidence(
    *, payment_id, checkpoint, verification_key
):
    identifier = _uuid(payment_id)
    if identifier is None:
        return None

    if not candidate_signed_checkpoint_matches(
        checkpoint=checkpoint,
        verification_key=verification_key,
    ):
        return None

    result = candidate_checkpoint_checked_payroll_evidence(
        payment_id=identifier,
        anchor_sequence=checkpoint["sequence"],
        anchor_digest=checkpoint["digest"],
    )
    if result is None:
        return None

    if result.get("earning_date_authorized") is not False:
        return None
    if result.get("checkpoint_source_authenticated") is not False:
        return None

    return {
        **result,
        "test_signature_matches_supplied_key": True,
        "checkpoint_key_id": checkpoint["key_id"],
        "checkpoint_source_authenticated": False,
        "external_audit_anchor_verified": False,
        "earning_date_authorized": False,
        "review_status": (
            "SIGNED_WITH_TEST_KEY_SOURCE_UNAUTHENTICATED"
        ),
    }


def signed_checkpoint_grants_live_access(*args, **kwargs):
    return False