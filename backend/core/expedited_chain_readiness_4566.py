"""Read-only integrity assessment of the expedited decision chain.

This records administrative review only, never customer consent,
cancellation waiver, equipment trust, or installation authority.
"""
from .documents import canonical_hash
from .expedited_service_request_4565 import KIND as REQUEST
from .expedited_service_review_4565 import REVIEW_KIND as REVIEW
from .expedited_manager_decision_4565 import DECISION_KIND as DECISION
from .models import ProjectEvidence


def assess_expedited_chain(project):
    denied = {
        "expedited_chain_reviewed": False,
        "expedited_authorized": False,
        "installation_authorized": False,
    }
    msr = getattr(project, "current_approved", None)
    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or getattr(project, "state", None) == "CANCELLED"
    ):
        return denied

    rows = list(ProjectEvidence.objects.filter(
        msr=msr, kind__in=(REQUEST, REVIEW, DECISION),
    ))
    groups = {
        kind: [row for row in rows if row.kind == kind]
        for kind in (REQUEST, REVIEW, DECISION)
    }
    if any(len(group) != 1 for group in groups.values()):
        return denied

    req, rev, dec = (groups[kind][0] for kind in (REQUEST, REVIEW, DECISION))
    snapshot_hash = canonical_hash(msr.snapshot)

    for record in (req, rev, dec):
        data = record.data
        if (
            type(data) is not dict
            or record.digest != canonical_hash(data)
            or record.msr_id != msr.pk
            or data.get("project_id") != str(project.pk)
            or data.get("msr_id") != str(msr.pk)
            or data.get("msr_version") != msr.number
            or data.get("snapshot_sha256") != snapshot_hash
            or any(data.get(key) is not False for key in (
                "customer_initials_verified",
                "document_signature_verified",
                "cancellation_protections_verified",
                "expedited_authorized",
                "installation_authorized",
            ))
        ):
            return denied

    if (
        req.data.get("status") != "PENDING_INDEPENDENT_VERIFICATION"
        or rev.data.get("status") != "CANDIDATE_ACCEPTED"
        or dec.data.get("status") != "MANAGER_APPROVED_PENDING_CUSTOMER_EVIDENCE"
        or rev.data.get("request_id") != str(req.pk)
        or rev.data.get("request_digest") != req.digest
        or dec.data.get("request_id") != str(req.pk)
        or dec.data.get("request_digest") != req.digest
        or dec.data.get("review_id") != str(rev.pk)
        or dec.data.get("review_digest") != rev.digest
        or req.created_by_id == rev.created_by_id
        or rev.data.get("reviewer_id") != str(rev.created_by_id)
        or req.data.get("requested_by") != str(req.created_by_id)
        or req.data.get("proposed_date") != rev.data.get("proposed_date")
        or rev.data.get("proposed_date") != dec.data.get("proposed_date")
    ):
        return denied

    return {**denied, "expedited_chain_reviewed": True}
