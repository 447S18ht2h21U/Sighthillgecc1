"""Conservative evidence labels for individual compensation reporting.

This is pure classification logic only.

It does not query a database, grant access, modify payment records,
verify signatures, or establish historical MSR attribution.
"""


def project_association_label(has_explicit_project):
    """Describe only whether a payment has an explicit project link."""

    if type(has_explicit_project) is not bool:
        raise ValueError("Project association must be a boolean.")

    if has_explicit_project:
        return "Project-associated"

    return "Not assigned to a project"


def historical_msr_label(has_explicit_historical_binding):
    """Never infer historical MSR attribution from a current MSR."""

    if type(has_explicit_historical_binding) is not bool:
        raise ValueError("Historical MSR binding must be a boolean.")

    if has_explicit_historical_binding:
        return "Historical MSR binding recorded"

    return "Historical MSR version not established"


def payment_evidence_label(
    status,
    issuance_recorded,
    settlement_verified,
    *,
    contractor,
):
    """Describe recorded payment state without inventing settlement.

    For employees, the current payroll workflow uses authorized
    issuance and a separate Comptroller PAID transition.

    For contractors, independent bank-settlement verification is
    required before the PAID transition.
    """

    if status not in ("DRAFT", "APPROVED", "PAID"):
        raise ValueError("Unknown compensation payment status.")

    for value in (
        issuance_recorded,
        settlement_verified,
        contractor,
    ):
        if type(value) is not bool:
            raise ValueError("Payment evidence flags must be booleans.")

    if settlement_verified and not contractor:
        raise ValueError(
            "Contractor settlement verification cannot describe employee payroll."
        )

    if settlement_verified and not issuance_recorded:
        raise ValueError(
            "Settlement verification requires issuance evidence."
        )

    if status == "DRAFT":
        if issuance_recorded or settlement_verified:
            raise ValueError("Draft compensation cannot have payment evidence.")
        return "Draft - Not Approved"

    if status == "APPROVED":
        if settlement_verified:
            return "Settlement Verified - Not Yet Marked Paid"
        if issuance_recorded:
            return "Payment Issued - Not Yet Marked Paid"
        return "Approved - Not Yet Issued"

    if not issuance_recorded:
        raise ValueError(
            "PAID compensation requires payment issuance evidence."
        )

    if contractor and not settlement_verified:
        raise ValueError(
            "PAID contractor compensation requires settlement verification."
        )

    return "Paid"


def installation_completion_evidence_label(provider_verified):
    """Keep trusted signature evidence distinct from manual attestation."""

    if type(provider_verified) is not bool:
        raise ValueError("Provider verification must be a boolean.")

    if provider_verified:
        return "Provider-Verified Completion"

    return "Provider-Verified Completion Not Established"