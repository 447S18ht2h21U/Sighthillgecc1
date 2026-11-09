"""Test-only anti-rollback comparison for historical payroll evidence.

The supplied minimum checkpoint is NOT independently authenticated.
This code proves only consistency with a supplied prior reference.
Trusted external storage, key custody, freshness, anti-replay, and
issuer-controlled monotonic updates are not implemented.

Never register this as a live payroll endpoint or authorization.
"""
import re

from .models import AuditEvent
from .payroll_technical_provenance_4296 import _uuid
from .payroll_checkpoint_key_custody_4313 import (
    candidate_registered_checkpoint_evidence,
)

_FIELDS = frozenset({
    "issuer_id",
    "key_id",
    "minimum_sequence",
    "minimum_digest",
})


def candidate_antirollback_payroll_evidence(
    *, payment_id, checkpoint, registry, expected_issuer,
    trusted_minimum
):
    identifier = _uuid(payment_id)
    if identifier is None:
        return None
    if type(checkpoint) is not dict:
        return None
    if type(trusted_minimum) is not dict:
        return None
    if set(trusted_minimum) != _FIELDS:
        return None
    if type(expected_issuer) is not str or not expected_issuer.strip():
        return None

    issuer = trusted_minimum.get("issuer_id")
    key_id = trusted_minimum.get("key_id")
    floor = trusted_minimum.get("minimum_sequence")
    floor_digest = trusted_minimum.get("minimum_digest")

    if issuer != expected_issuer:
        return None
    if type(key_id) is not str or key_id != checkpoint.get("key_id"):
        return None
    if type(floor) is not int or floor < 1:
        return None
    if (
        type(floor_digest) is not str
        or re.fullmatch(r"[0-9a-f]{64}", floor_digest) is None
    ):
        return None

    checkpoint_sequence = checkpoint.get("sequence")
    if (
        type(checkpoint_sequence) is not int
        or checkpoint_sequence < floor
    ):
        return None

    # A supplied prior reference must match the actual historical
    # event at that sequence. This does not authenticate its origin.
    historical = AuditEvent.objects.filter(sequence=floor).first()
    if historical is None or historical.digest != floor_digest:
        return None

    if (
        checkpoint_sequence == floor
        and checkpoint.get("digest") != floor_digest
    ):
        return None

    evidence = candidate_registered_checkpoint_evidence(
        payment_id=identifier,
        checkpoint=checkpoint,
        registry=registry,
        expected_issuer=expected_issuer,
    )
    if evidence is None:
        return None

    if evidence.get("earning_date_authorized") is not False:
        return None

    return {
        **evidence,
        "minimum_sequence_checked": floor,
        "test_minimum_reference_matched": True,
        "minimum_reference_source_authenticated": False,
        "registry_source_authenticated": False,
        "external_audit_anchor_verified": False,
        "earning_date_authorized": False,
        "review_status": (
            "ANTIROLLBACK_TEST_REFERENCE_NOT_AUTHENTICATED"
        ),
    }


def antirollback_candidate_grants_live_access(*args, **kwargs):
    return False