"""Isolated custody retrieval adapter with fail-closed transport handling.

The fetcher is caller-injected and entirely untrusted. This module
does not provide secure transport, certificate validation, authenticated
custody, durable storage, or operational payroll authority.

No production network service or route is configured.
"""
import re

from .payroll_external_custody_boundary_4319 import (
    candidate_custody_manifest,
)
from .payroll_custody_readback_4321 import (
    candidate_custody_readback_review,
)

_RESPONSE_FIELDS = frozenset({
    "object_id", "custodian_id", "manifest", "receipt",
})


def candidate_custody_object_id(manifest):
    """Deterministic test object reference; not proof of custody."""
    if type(manifest) is not dict:
        return None

    digest = manifest.get("manifest_sha256")
    if (
        type(digest) is not str
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
    ):
        return None

    return "audit-checkpoint/" + digest


def candidate_transport_custody_review(
    *, payment_id, checkpoint, registry, expected_issuer,
    trusted_minimum, receipt, expected_custodian, fetcher
):
    if not callable(fetcher):
        return None

    if (
        type(expected_custodian) is not str
        or re.fullmatch(
            r"[A-Za-z0-9_-]{1,64}", expected_custodian
        ) is None
    ):
        return None

    manifest = candidate_custody_manifest()
    if manifest is None:
        return None

    object_id = candidate_custody_object_id(manifest)
    if object_id is None:
        return None

    request = {
        "object_id": object_id,
        "expected_custodian": expected_custodian,
    }

    # Test-only injected transport. All failures deny the candidate.
    try:
        response = fetcher(dict(request))
    except Exception:
        return None

    if type(response) is not dict:
        return None
    if set(response) != _RESPONSE_FIELDS:
        return None

    if response.get("object_id") != object_id:
        return None
    if response.get("custodian_id") != expected_custodian:
        return None

    readback = {
        "custodian_id": response["custodian_id"],
        "manifest": response["manifest"],
        "receipt": response["receipt"],
    }

    result = candidate_custody_readback_review(
        payment_id=payment_id,
        checkpoint=checkpoint,
        registry=registry,
        expected_issuer=expected_issuer,
        trusted_minimum=trusted_minimum,
        receipt=receipt,
        readback=readback,
        expected_custodian=expected_custodian,
    )
    if result is None:
        return None

    if (
        result.get("external_custodian_authenticated") is not False
        or result.get("earning_date_authorized") is not False
        or result.get("payroll_access_authorized") is not False
    ):
        return None

    return {
        **result,
        "test_requested_object_id": object_id,
        "test_transport_fields_matched": True,
        "transport_peer_authenticated": False,
        "external_custodian_authenticated": False,
        "durable_external_storage_verified": False,
        "earning_date_authorized": False,
        "payroll_access_authorized": False,
        "review_status": "TEST_TRANSPORT_MATCHED_EXTERNAL_TRUST_ABSENT",
    }


def transport_candidate_grants_live_access(*args, **kwargs):
    return False