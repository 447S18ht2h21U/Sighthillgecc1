"""Test-only payroll lineage requiring the complete original audit chain.

Fail closed when hash, sequence, audit-head or outbox verification fails.
The evidence is still a provisional candidate, not a certified earning
date, an external audit attestation, or permission to view or pay payroll.

No live route or operational access is registered by this module.
"""
from .payroll_technical_provenance_4296 import _uuid
from .payroll_audit_chain_4309 import candidate_complete_audit_chain
from .payroll_earning_timeline_review_4307 import (
    candidate_earning_timeline_review,
)


def candidate_audit_verified_earning_lineage(*, payment_id):
    identifier = _uuid(payment_id)
    if identifier is None:
        return None

    if candidate_complete_audit_chain() is not True:
        return None

    timeline = candidate_earning_timeline_review(
        payment_id=identifier
    )
    if timeline is None:
        return None

    if timeline.get("earning_date_authorized") is not False:
        return None
    if timeline.get("review_status") != (
        "HUMAN_REVIEW_REQUIRED_TEST_ONLY"
    ):
        return None

    if timeline.get("payment_record_id") != str(identifier):
        return None

    return {
        **timeline,
        "database_audit_chain_consistent": True,
        "external_audit_anchor_verified": False,
        "earning_date_authorized": False,
        "review_status": "AUDIT_CHECKED_HUMAN_REVIEW_REQUIRED_TEST_ONLY",
    }


def audit_verified_lineage_grants_live_access(*args, **kwargs):
    """No audit result overrides the existing payroll access gates."""
    return False