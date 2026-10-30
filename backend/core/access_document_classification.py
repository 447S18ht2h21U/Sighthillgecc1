"""VERIDIAN document-access classification metadata.

This module maps document categories to proposed permission codes.
It neither verifies signatures nor grants access to document bytes.
Existing project-scoped backend authorization remains authoritative.
"""

from dataclasses import dataclass

from .access_permission_catalog import PERMISSION_BY_CODE
from .models import Document


@dataclass(frozen=True)
class DocumentAccessClassification:
    kind: str
    label: str
    view_permission: str
    generated_document_supported: bool
    signed_document_verified: bool = False


DOCUMENT_CLASSIFICATIONS = (
    DocumentAccessClassification(
        "CONTRACT",
        "Project SOW Agreement",
        "documents.sow.view",
        True,
    ),
    DocumentAccessClassification(
        "INVOICE",
        "Invoice",
        "documents.invoice.view",
        True,
    ),
    DocumentAccessClassification(
        "COMPLETION_FINANCED",
        "Financed Completion Certificate",
        "documents.completion_financed.view",
        True,
    ),
    DocumentAccessClassification(
        "COMPLETION_NON_FINANCED",
        "Non-Financed Completion Certificate",
        "documents.completion_non_financed.view",
        True,
    ),
    DocumentAccessClassification(
        "SATISFACTION_SURVEY",
        "Customer Satisfaction Survey",
        "documents.satisfaction_survey.view",
        False,
    ),
)

DOCUMENT_CLASSIFICATION_BY_KIND = {
    item.kind: item for item in DOCUMENT_CLASSIFICATIONS
}

if len(DOCUMENT_CLASSIFICATION_BY_KIND) != len(DOCUMENT_CLASSIFICATIONS):
    raise RuntimeError("Duplicate document access classification.")

existing_kinds = {value for value, label in Document.Kind.choices}
supported_kinds = {
    item.kind for item in DOCUMENT_CLASSIFICATIONS
    if item.generated_document_supported
}

if supported_kinds != existing_kinds:
    raise RuntimeError("Document classifications differ from generated kinds.")

for item in DOCUMENT_CLASSIFICATIONS:
    if item.view_permission not in PERMISSION_BY_CODE:
        raise RuntimeError("Unknown document-view permission.")

if DOCUMENT_CLASSIFICATION_BY_KIND[
    "SATISFACTION_SURVEY"
].generated_document_supported:
    raise RuntimeError("Survey generation is not implemented.")


def describe_document_kind(kind):
    """Classification only, not a signature or access assertion."""
    return DOCUMENT_CLASSIFICATION_BY_KIND.get(kind)


def document_access_granted(user, kind, *, project=None):
    """Fail closed until independent permission enforcement is approved."""
    return False
