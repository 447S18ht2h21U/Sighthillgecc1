"""Approved company identity for future VERIDIAN document versions.

This module does not alter existing approved PDF templates, signed
documents, or historical customer records. Applying these values to
new templates requires its own reviewed integration.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CompanyIdentity:
    legal_name: str
    email: str
    website: str | None


APPROVED_COMPANY_IDENTITY = CompanyIdentity(
    legal_name="Green Energy Contracting Corporation",
    email="care@gecc.cloud",
    website=None,
)
