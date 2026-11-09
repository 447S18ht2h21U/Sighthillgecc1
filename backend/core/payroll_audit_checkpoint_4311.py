"""Test-only comparison against a separately supplied audit checkpoint.

The checkpoint sequence and digest are compared against the original
GECC audit chain, including historical checkpoints preceding newer events.

A caller-provided reference is NOT independently authenticated.
This module cannot establish source trust, authorize earning dates,
certify financial records, or enable live payroll access.
"""
import re

from .models import AuditEvent
from .payroll_technical_provenance_4296 import _uuid
from .payroll_audit_chain_4309 import candidate_complete_audit_chain
from .payroll_audit_verified_lineage_4310 import (
    candidate_audit_verified_earning_lineage,
)


def candidate_checkpoint_matches(*, anchor_sequence, anchor_digest):
    """Compare with a supplied reference, without trusting its origin."""
    if type(anchor_sequence) is not int or anchor_sequence < 1:
        return False

    if (
        type(anchor_digest) is not str
        or re.fullmatch(r"[0-9a-f]{64}", anchor_digest) is None
    ):
        return False

    if candidate_complete_audit_chain() is not True:
        return False

    historical = AuditEvent.objects.filter(
        sequence=anchor_sequence
    ).first()

    if historical is None:
        return False

    return historical.digest == anchor_digest


def candidate_checkpoint_checked_payroll_evidence(
    *, payment_id, anchor_sequence, anchor_digest
):
    identifier = _uuid(payment_id)

    if identifier is None:
        return None

    if not candidate_checkpoint_matches(
        anchor_sequence=anchor_sequence,
        anchor_digest=anchor_digest,
    ):
        return None

    lineage = candidate_audit_verified_earning_lineage(
        payment_id=identifier
    )
    if lineage is None:
        return None

    if lineage.get("earning_date_authorized") is not False:
        return None

    return {
        **lineage,
        "checkpoint_sequence": anchor_sequence,
        "checkpoint_digest": anchor_digest,
        "checkpoint_comparison_passed": True,
        "checkpoint_source_authenticated": False,
        "external_audit_anchor_verified": False,
        "earning_date_authorized": False,
        "review_status": (
            "CHECKPOINT_MATCHED_SOURCE_UNAUTHENTICATED_TEST_ONLY"
        ),
    }


def checkpoint_comparison_grants_live_access(*args, **kwargs):
    return False