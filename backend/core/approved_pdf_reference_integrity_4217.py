"""Verified approved PDF references for future deployment integration.

Reads original PDFs only. Never modifies them, publishes documents,
changes a database, or authorizes signatures or delivery.
"""
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


APPROVED_PDFS = {
    "CUSTOMER_SOW": (
        "GECC Project Scope of Work ref1103a.pdf",
        "674A1F999133BFE36E216271C55A2A840248858E48700573C6FCE117E66554D9",
        2,
    ),
    "AGREEMENT": (
        "GECC Project  Agreement ref1103MD.pdf",
        "2A6B35102520CDE3937BC841D3393F7E0CBA06F9CA046AFC879E3152EA6BFF4C",
        3,
    ),
    "INVOICE": (
        "GECC Invoice ref1103.pdf",
        "F1C0FBD41858AF1BA863A9D16D31A1F7E8730E4A3267E2112575F3B9D923B42F",
        1,
    ),
    "RECEIPT": (
        "GECC Receipt ref1103.pdf",
        "AEB93EC3097E82BDD2B8B12D9476C2FCC465DC00A6D57A6D1AE49EDC8EA978CD",
        1,
    ),
    "COMPLETION_NON_FINANCED": (
        "Completion Certificate ref1103NF.pdf",
        "F6784EB635F00C17C13DAE21F3BFC937FAFE5086438E733C478C828667EA6579",
        1,
    ),
    "COMPLETION_FINANCED": (
        "Completion Certificate ref1103F.pdf",
        "C22586AEB3E1603F1EDFFF16F739F778B418856DA7414E67EEB2E3531EAB8D8A",
        1,
    ),
}


@dataclass(frozen=True)
class VerifiedPDFReference:
    kind: str
    filename: str
    sha256: str
    page_count: int
    form_field_names: tuple


def verify_reference(directory, kind):
    """Fail closed unless one exact approved original is present."""
    if kind not in APPROVED_PDFS:
        raise ValueError("Unknown approved document kind.")

    filename, expected_hash, expected_pages = APPROVED_PDFS[kind]
    directory = Path(directory)
    path = directory / filename

    if path.is_symlink() or not path.is_file():
        raise ValueError("Approved PDF original is missing or redirected.")

    content = path.read_bytes()
    actual_hash = sha256(content).hexdigest().upper()

    if actual_hash != expected_hash:
        raise ValueError("Approved PDF fingerprint mismatch.")

    reader = PdfReader(BytesIO(content), strict=True)

    if reader.is_encrypted:
        raise ValueError("Encrypted approved PDF is unsupported.")

    if len(reader.pages) != expected_pages:
        raise ValueError("Approved PDF page count mismatch.")

    fields = reader.get_fields() or {}
    names = tuple(sorted(str(name) for name in fields))

    return VerifiedPDFReference(
        kind=kind,
        filename=filename,
        sha256=actual_hash,
        page_count=expected_pages,
        form_field_names=names,
    )


def verify_all_references(directory):
    """Verify all six originals; reject extra PDFs in the reference folder."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError("Approved reference directory missing.")

    expected = {entry[0] for entry in APPROVED_PDFS.values()}
    actual = {path.name for path in directory.glob("*.pdf")}

    if actual != expected:
        raise ValueError("Approved PDF reference inventory mismatch.")

    return {
        kind: verify_reference(directory, kind)
        for kind in APPROVED_PDFS
    }