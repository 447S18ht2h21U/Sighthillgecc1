"""Development-only six-document compatibility policy.

This module does not modify Document.Kind, register a route, create
database records, authorize release, sign, or deliver documents.

Legacy operational categories remain unchanged. A mapping is a
compatibility description, never permission to generate or release.
"""
from dataclasses import dataclass


class CompatibilityDenied(ValueError):
    """Unsupported or unsafe document compatibility request."""


@dataclass(frozen=True)
class DocumentCompatibility:
    approved_kind: str
    legacy_kind: str | None
    operationally_integrated: bool = False
    review_only: bool = True
    release_authorized: bool = False


# Explicit correspondence only. CUSTOMER_SOW and RECEIPT are distinct
# approved forms and must not be silently stored as another document.
_KIND_MAP = {
    "CUSTOMER_SOW": None,
    "AGREEMENT": "CONTRACT",
    "INVOICE": "INVOICE",
    "RECEIPT": None,
    "COMPLETION_NON_FINANCED": "COMPLETION_NON_FINANCED",
    "COMPLETION_FINANCED": "COMPLETION_FINANCED",
}


def describe_compatibility(kind):
    """Return a non-operational description of an approved form."""
    if type(kind) is not str or kind not in _KIND_MAP:
        raise CompatibilityDenied("Unrecognized approved document kind.")

    return DocumentCompatibility(
        approved_kind=kind,
        legacy_kind=_KIND_MAP[kind],
    )


def require_exact_approved_kind(kind, expected_kind):
    """Reject document substitutions, including Receipt/Invoice swaps."""
    actual = describe_compatibility(kind)
    expected = describe_compatibility(expected_kind)

    if actual.approved_kind != expected.approved_kind:
        raise CompatibilityDenied(
            "Document identity mismatch. Substitution is prohibited."
        )

    return actual


def require_operational_integration(kind):
    """Fail closed until separately approved operational integration."""
    describe_compatibility(kind)
    raise CompatibilityDenied(
        "Six-document operational integration is not authorized."
    )