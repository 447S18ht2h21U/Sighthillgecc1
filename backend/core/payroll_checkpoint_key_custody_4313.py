"""Test-only signing-key custody boundary for payroll evidence.

The registry is supplied by the test, not authenticated or stored
in a trusted production environment. Even a successful comparison
cannot establish independent custody or authorize payroll access.

A production design must use separately controlled key custody,
authenticated issuer identity, trusted revocation history, and
anti-rollback protection. No live API is registered here.
"""
from .payroll_signed_checkpoint_4312 import (
    candidate_signed_checkpoint_payroll_evidence,
)
from .payroll_technical_provenance_4296 import _uuid

_REQUIRED = frozenset({
    "key_id",
    "issuer_id",
    "purpose",
    "verification_key",
    "revoked",
    "first_sequence",
    "last_sequence",
})
_PURPOSE = "AUDIT_CHECKPOINT_VERIFICATION_TEST_ONLY"


def candidate_registered_checkpoint_evidence(
    *, payment_id, checkpoint, registry, expected_issuer
):
    identifier = _uuid(payment_id)
    if identifier is None or type(checkpoint) is not dict:
        return None
    if type(registry) is not dict or type(expected_issuer) is not str:
        return None
    if not expected_issuer.strip():
        return None

    key_id = checkpoint.get("key_id")
    sequence = checkpoint.get("sequence")

    if type(key_id) is not str or type(sequence) is not int:
        return None

    entry = registry.get(key_id)
    if type(entry) is not dict or set(entry) != _REQUIRED:
        return None

    if entry.get("key_id") != key_id:
        return None
    if entry.get("issuer_id") != expected_issuer:
        return None
    if entry.get("purpose") != _PURPOSE:
        return None
    if entry.get("revoked") is not False:
        return None

    first = entry.get("first_sequence")
    last = entry.get("last_sequence")

    if type(first) is not int or first < 1:
        return None
    if last is not None and (
        type(last) is not int or last < first
    ):
        return None
    if sequence < first:
        return None
    if last is not None and sequence > last:
        return None

    verification_key = entry.get("verification_key")
    if type(verification_key) is not bytes:
        return None
    if len(verification_key) < 32:
        return None

    evidence = candidate_signed_checkpoint_payroll_evidence(
        payment_id=identifier,
        checkpoint=checkpoint,
        verification_key=verification_key,
    )
    if evidence is None:
        return None
    if evidence.get("earning_date_authorized") is not False:
        return None

    return {
        **evidence,
        "test_registry_key_matched": True,
        "test_registry_issuer": expected_issuer,
        "test_registry_purpose": _PURPOSE,
        "test_registry_revoked": False,
        "registry_source_authenticated": False,
        "checkpoint_source_authenticated": False,
        "external_audit_anchor_verified": False,
        "earning_date_authorized": False,
        "review_status": (
            "TEST_REGISTRY_MATCHED_NO_INDEPENDENT_CUSTODY"
        ),
    }


def custody_candidate_grants_live_access(*args, **kwargs):
    return False