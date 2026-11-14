"""Unsigned internal Installation Inspection Attestation PDF.

The printed DocuSign anchor is NOT a signature or provider evidence.
No envelope creation, sending, trust promotion, or Receipt authorization.
"""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from .documents import canonical_hash
from .installation_attestation_manifest_4941 import (
    InstallationSigningManifest,
    build_installation_signing_manifest,
)


SIGNATURE_ANCHOR = "/IM_ATTEST_SIG_4942/"
DATE_ANCHOR = "/IM_ATTEST_DATE_4942/"


@dataclass(frozen=True)
class UnsignedInstallationAttestation:
    project_id: str
    approved_msr_id: str
    source_pdf_sha256: str
    manifest_sha256: str
    pdf_sha256: str
    content: bytes
    status: str = "UNSIGNED_INTERNAL_ATTESTATION"
    signature_anchor: str = SIGNATURE_ANCHOR
    date_anchor: str = DATE_ANCHOR
    envelope_created: bool = False
    signature_verified: bool = False
    source_artifact_authenticated: bool = False
    trusted_installation_evidence: bool = False
    final_receipt_issuance_authorized: bool = False
    completion_authorized: bool = False


def _validated_manifest(manifest):
    if type(manifest) is not InstallationSigningManifest:
        raise ValidationError("Verified installation signing manifest required.")

    if (
        manifest.status != "OFFLINE_MANIFEST_NOT_SENT"
        or manifest.source_document_role != "SUPPORTING_SOURCE_NOT_SIGNED"
        or manifest.attestation_pdf_created is not False
        or manifest.envelope_created is not False
        or manifest.signer_authenticated is not False
        or manifest.source_artifact_authenticated is not False
        or manifest.trusted_installation_evidence is not False
        or manifest.final_receipt_issuance_authorized is not False
        or manifest.completion_authorized is not False
    ):
        raise ValidationError("Manifest asserted unsupported authority.")

    pdf = manifest.source_pdf
    if (
        type(pdf) is not bytes
        or len(pdf) < 8
        or len(pdf) > 1024 * 1024
        or not pdf.startswith(b"%PDF-")
        or not pdf.rstrip().endswith(b"%%EOF")
        or sha256(pdf).hexdigest() != manifest.source_pdf_sha256
    ):
        raise ValidationError("Exact retained inspection PDF mismatch.")

    required_ids = (
        manifest.project_id,
        manifest.approved_msr_id,
        manifest.preparation_evidence_id,
        manifest.source_evidence_id,
        manifest.signer_user_id,
    )
    if any(type(value) is not str or not value.strip() for value in required_ids):
        raise ValidationError("Installation binding identity missing.")

    if (
        type(manifest.approved_msr_version) is not int
        or manifest.approved_msr_version < 1
        or type(manifest.signer_name) is not str
        or not 2 <= len(manifest.signer_name.strip()) <= 100
        or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", manifest.signer_email)
        or any(c in manifest.signer_name for c in "\r\n")
        or any(c in manifest.signer_email for c in "\r\n")
        or not re.fullmatch(r"[0-9a-f]{64}", manifest.attestation_binding_sha256)
    ):
        raise ValidationError("Installation Manager signing identity invalid.")

    identity = {
        "purpose": "DOCUSIGN_INSTALLATION_SIGNING_MANIFEST_4941",
        "project_id": manifest.project_id,
        "approved_msr_id": manifest.approved_msr_id,
        "approved_msr_version": manifest.approved_msr_version,
        "preparation_evidence_id": manifest.preparation_evidence_id,
        "source_evidence_id": manifest.source_evidence_id,
        "source_pdf_sha256": manifest.source_pdf_sha256,
        "signer_user_id": manifest.signer_user_id,
        "signer_email": manifest.signer_email,
        "signer_name": manifest.signer_name,
        "attestation_binding_sha256": manifest.attestation_binding_sha256,
        "source_document_role": "SUPPORTING_SOURCE_NOT_SIGNED",
    }

    if canonical_hash(identity) != manifest.manifest_sha256:
        raise ValidationError("Installation signing manifest fingerprint mismatch.")


def _field(pdf, label, value, y):
    pdf.setFont("Helvetica-Bold", 9)
    pdf.setFillColor(colors.HexColor("#142B3B"))
    pdf.drawString(54, y, label)

    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.black)
    value = str(value)

    if stringWidth(value, "Helvetica", 9) > 490:
        raise ValidationError("Attestation identity too long for PDF.")

    pdf.drawString(54, y - 16, value)
    return y - 40


def render_unsigned_installation_attestation(*, actor, project_id):
    """Render from actual verified persisted evidence, without signing."""
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Installation attestation rendering disabled.")

    manifest = build_installation_signing_manifest(
        actor=actor, project_id=project_id
    )
    _validated_manifest(manifest)

    output = BytesIO()
    pdf = canvas.Canvas(
        output,
        pagesize=letter,
        pageCompression=0,
        invariant=1,
    )
    width, height = letter

    pdf.setTitle("GECC Installation Manager Post-Installation Inspection and Certification")
    pdf.setAuthor("Green Energy Contracting Corporation")

    pdf.setFillColor(colors.HexColor("#142B3B"))
    pdf.rect(0, height - 108, width, 108, fill=1, stroke=0)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(54, height - 44, "Green Energy Contracting Corporation")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(54, height - 70, "Post-Installation Inspection & Certification")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(54, height - 90, "INTERNAL - UNSIGNED - NOT RELEASED")

    y = height - 145
    y = _field(pdf, "Project ID", manifest.project_id, y)
    y = _field(
        pdf, "Approved MSR / Version",
        f"{manifest.approved_msr_id} / {manifest.approved_msr_version}", y
    )
    y = _field(
        pdf, "Installation source evidence ID",
        manifest.source_evidence_id, y
    )
    y = _field(
        pdf, "Source PDF SHA-256",
        manifest.source_pdf_sha256, y
    )
    y = _field(
        pdf, "Attestation preparation fingerprint",
        manifest.attestation_binding_sha256, y
    )

    pdf.setFillColor(colors.HexColor("#087F75"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(54, y - 2, "INSTALLATION MANAGER CERTIFICATION")

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica", 9)
    paragraphs = (
        "I certify that I personally conducted the post-installation "
        "inspection of the project identified above.",

        "I verified the installed equipment against the approved Project "
        "Scope of Work, reviewed the installation for completeness, and "
        "documented any deficiencies or corrective work required.",

        "The inspection findings recorded in the associated inspection "
        "report accurately reflect my observations at the time of inspection.",

        "By signing electronically through DocuSign, I certify the accuracy "
        "of these statements and acknowledge my responsibility for the "
        "inspection findings.",
    )

    from reportlab.lib.utils import simpleSplit

    y -= 26
    for paragraph in paragraphs:
        lines = simpleSplit(paragraph, "Helvetica", 9, 498)
        for line in lines:
            pdf.drawString(54, y, line)
            y -= 14
        y -= 7

    y -= 12
    y = _field(pdf, "Installation Manager", manifest.signer_name, y)
    y = _field(pdf, "Signer email", manifest.signer_email, y)

    if y - 48 < 78:
        raise ValidationError("Certification exceeds one-page layout.")

    pdf.setStrokeColor(colors.HexColor("#087F75"))
    pdf.roundRect(54, y - 48, 504, 66, 6, fill=0, stroke=1)
    pdf.setFillColor(colors.HexColor("#142B3B"))
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(66, y + 1, "Reserved for DocuSign signature and date")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(66, y - 17, SIGNATURE_ANCHOR)
    pdf.drawString(300, y - 17, DATE_ANCHOR)

    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(colors.HexColor("#555555"))
    pdf.drawString(
        54, 56,
        "Unsigned draft. Signing fields must be configured in DocuSign."
    )
    pdf.drawString(
        54, 42,
        "Source integrity alone does not authenticate installation completion."
    )

    pdf.showPage()
    pdf.save()
    content = output.getvalue()

    if (
        not content.startswith(b"%PDF-")
        or not content.rstrip().endswith(b"%%EOF")
        or SIGNATURE_ANCHOR.encode() not in content
        or DATE_ANCHOR.encode() not in content
    ):
        raise ValidationError("Rendered attestation PDF integrity failed.")

    return UnsignedInstallationAttestation(
        project_id=manifest.project_id,
        approved_msr_id=manifest.approved_msr_id,
        source_pdf_sha256=manifest.source_pdf_sha256,
        manifest_sha256=manifest.manifest_sha256,
        pdf_sha256=sha256(content).hexdigest(),
        content=content,
    )
