"""Unregistered CEO tax-verification readiness review.

This is a read-only preliminary check of an untrusted in-memory candidate.
It is NOT verification, authorization to verify, or proof of persisted evidence.
"""
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role, User
from .tax_draft_evidence_4437U import evidence_package_digest_matches


def review_ceo_tax_verification_candidate(actor, candidate):
    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("A registered CEO is required.")

    verifier = User.objects.filter(pk=actor.pk).first()

    if (
        verifier is None
        or verifier.is_active is not True
        or verifier.role != Role.CEO
    ):
        raise PermissionDenied("Only the active CEO may review tax verification.")

    if not evidence_package_digest_matches(candidate):
        raise ValidationError("Tax draft evidence fingerprint mismatch.")

    payload = candidate["payload"]

    if type(payload) is not dict:
        raise ValidationError("Invalid draft evidence.")

    if (
        payload.get("status") != "UNVERIFIED_DRAFT_EVIDENCE_ONLY"
        or payload.get("schema") != "VERIDIAN_TAX_DRAFT_EVIDENCE_4437U_V1"
        or payload.get("independent_tax_entry_verified") is not False
        or payload.get("financial_report_eligible") is not False
        or payload.get("tax_posting_authorized") is not False
        or payload.get("tax_filing_authorized") is not False
        or payload.get("tax_payment_authorized") is not False
    ):
        raise ValidationError("Candidate is not eligible for preliminary review.")

    preparer_id = payload.get("prepared_by")
    if type(preparer_id) is not str or not preparer_id:
        raise ValidationError("Recorded preparer identity is missing.")

    preparer = User.objects.filter(pk=preparer_id).first()

    if (
        preparer is None
        or preparer.role != Role.COMPTROLLER
        or str(preparer.pk) == str(verifier.pk)
    ):
        raise PermissionDenied("An independent Comptroller preparer is required.")

    # A matching digest is NOT an authenticated signature. The caller can
    # recompute a digest. No approval is allowed without trusted persistence.
    return {
        "status": "PRELIMINARY_REVIEW_ONLY",
        "verifier_role": "CEO",
        "preparer_role": "COMPTROLLER",
        "different_people": True,
        "evidence_digest_matches": True,
        "persisted_entry_authenticated": False,
        "independent_tax_entry_verified": False,
        "verification_authorized": False,
        "financial_report_eligible": False,
        "tax_posting_authorized": False,
        "tax_filing_authorized": False,
        "tax_payment_authorized": False,
    }
