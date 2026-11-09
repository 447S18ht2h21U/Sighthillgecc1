"""Read-only PDF integrity and lifecycle review.

No ORM writes, operational routes, signing, customer delivery, or release.
"""
from hashlib import sha256
from io import BytesIO

from pypdf import PdfReader

from .approved_document_lifecycle_4248 import (
    LifecycleDenied,
    inspect_fictional_document_lifecycle,
)


def inspect_integrated_document_lifecycle(batch):
    """Verify six actual PDFs without turning previews into evidence."""
    report = inspect_fictional_document_lifecycle(batch)

    for item, entry in zip(report.documents, batch["manifest"]):
        content = batch["pdfs"][item.kind]

        fingerprint = sha256(content).hexdigest().upper()
        if entry.get("sha256") != fingerprint:
            raise LifecycleDenied("Document PDF fingerprint mismatch.")

        pages = entry.get("pages")
        if type(pages) is not int or pages < 1:
            raise LifecycleDenied("Invalid document page count.")

        try:
            reader = PdfReader(BytesIO(content), strict=True)
            actual_pages = len(reader.pages)
        except Exception as exc:
            raise LifecycleDenied("Invalid document PDF structure.") from exc

        if actual_pages != pages:
            raise LifecycleDenied("Document PDF page count mismatch.")

    return report