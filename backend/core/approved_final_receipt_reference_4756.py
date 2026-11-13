"""Immutable-reference verification for the approved GECC V4 Receipt.

This service does not issue a Receipt, assert payment, send email,
authenticate delivery, or authorize administrative completion.
"""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


APPROVED_FILENAME = "GECC Receipt 20261107v4-survey-corrected.pdf"
APPROVED_SHA256 = (
    "02F94BA72A5FAE593278A2C781659FC97B0001A692216C8780D066C38155E300"
)
APPROVED_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "reference"
    / "GECC-20261107-v4-survey-corrected"
)

REQUIRED_SURVEY_TEXT = (
    "Did we clean up after our work?",
    "Were we professional?",
    "Would you refer us to a friend?",
)


@dataclass(frozen=True)
class VerifiedFinalReceiptReference:
    filename: str
    sha256: str
    page_count: int
    width: float
    height: float
    content: bytes


def verify_final_receipt_bytes(content):
    """Reject altered, incomplete, or incorrectly formatted originals."""
    if not isinstance(content, bytes) or not content.startswith(b"%PDF-"):
        raise ValueError("Approved Receipt PDF bytes required.")

    digest = sha256(content).hexdigest().upper()

    if digest != APPROVED_SHA256:
        raise ValueError("Approved V4 Receipt fingerprint mismatch.")

    reader = PdfReader(BytesIO(content), strict=True)

    if reader.is_encrypted or len(reader.pages) != 1:
        raise ValueError("Approved Receipt must be one unencrypted page.")

    page = reader.pages[0]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)

    if (width, height) != (792.0, 612.0):
        raise ValueError("Approved Receipt landscape geometry changed.")

    visible = " ".join((page.extract_text() or "").split())

    if "SURVEY:" not in visible:
        raise ValueError("Approved Receipt survey heading missing.")

    for phrase in REQUIRED_SURVEY_TEXT:
        if phrase not in visible:
            raise ValueError("Approved Receipt survey content changed.")

    survey = visible.split("SURVEY:", 1)[1]

    if any(f"{number}. " in survey for number in (1, 2, 3)):
        raise ValueError("Outdated numbered survey detected.")

    return VerifiedFinalReceiptReference(
        filename=APPROVED_FILENAME,
        sha256=digest,
        page_count=1,
        width=width,
        height=height,
        content=content,
    )


def verify_approved_final_receipt():
    """Read only the explicitly approved original at its fixed path."""
    path = APPROVED_DIRECTORY / APPROVED_FILENAME

    if path.is_symlink() or not path.is_file():
        raise ValueError("Approved V4 Receipt file missing or redirected.")

    return verify_final_receipt_bytes(path.read_bytes())
