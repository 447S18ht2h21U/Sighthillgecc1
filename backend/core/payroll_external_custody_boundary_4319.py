"""Test-only, provider-independent external audit custody boundary.

Creates a deterministic manifest from the ORIGINAL current audit head
only after verifying the complete database audit chain.

A returned receipt is untrusted application input. Matching hashes
do NOT authenticate a custodian, establish secure delivery, guarantee
durable storage, or grant payroll authority.

No network, credentials, production storage, or live APIs are used.
"""
import hashlib
import json
import re

from .models import AuditHead
from .payroll_audit_chain_4309 import candidate_complete_audit_chain

_SCHEMA = "VERIDIAN_TEST_CUSTODY_MANIFEST_V1"
_ENVIRONMENT = "ISOLATED_TEST"
_RECEIPT_FIELDS = frozenset({
    "manifest_sha256",
    "custodian_id",
    "acknowledged_sequence",
})


def _canonical_bytes(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def candidate_custody_manifest():
    """Create an informational test manifest, without writing anything."""
    if candidate_complete_audit_chain() is not True:
        return None

    heads = list(AuditHead.objects.all())
    if len(heads) != 1 or heads[0].pk != 1:
        return None

    head = heads[0]
    if type(head.sequence) is not int or head.sequence < 1:
        return None
    if (
        type(head.digest) is not str
        or re.fullmatch(r"[0-9a-f]{64}", head.digest) is None
    ):
        return None

    body = {
        "schema": _SCHEMA,
        "environment": _ENVIRONMENT,
        "audit_sequence": head.sequence,
        "audit_digest": head.digest,
    }
    body["manifest_sha256"] = hashlib.sha256(
        _canonical_bytes(body)
    ).hexdigest()

    return body


def candidate_custody_receipt_comparison(*, manifest, receipt):
    """Compare untrusted receipt fields; never attest external custody."""
    if type(manifest) is not dict or type(receipt) is not dict:
        return None
    if set(manifest) != {
        "schema", "environment", "audit_sequence",
        "audit_digest", "manifest_sha256",
    }:
        return None
    if (
        manifest.get("schema") != _SCHEMA
        or manifest.get("environment") != _ENVIRONMENT
    ):
        return None

    if set(receipt) != _RECEIPT_FIELDS:
        return None

    sequence = manifest.get("audit_sequence")
    digest = manifest.get("audit_digest")
    fingerprint = manifest.get("manifest_sha256")

    if type(sequence) is not int or sequence < 1:
        return None
    if (
        type(digest) is not str
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
    ):
        return None
    if (
        type(fingerprint) is not str
        or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
    ):
        return None

    base = {
        "schema": _SCHEMA,
        "environment": _ENVIRONMENT,
        "audit_sequence": sequence,
        "audit_digest": digest,
    }
    expected = hashlib.sha256(
        _canonical_bytes(base)
    ).hexdigest()

    if fingerprint != expected:
        return None

    custodian = receipt.get("custodian_id")
    if (
        type(custodian) is not str
        or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", custodian) is None
    ):
        return None

    if receipt.get("acknowledged_sequence") != sequence:
        return None
    if type(receipt.get("acknowledged_sequence")) is not int:
        return None
    if receipt.get("manifest_sha256") != fingerprint:
        return None

    return {
        "receipt_fields_match": True,
        "claimed_custodian": custodian,
        "external_custodian_authenticated": False,
        "durable_external_storage_verified": False,
        "earning_date_authorized": False,
        "payroll_access_authorized": False,
        "status": "TEST_ONLY_UNTRUSTED_RECEIPT_COMPARISON",
    }


def external_custody_boundary_grants_live_access(*args, **kwargs):
    return False