"""Approved internal inspection form: offline PDF and corrective-action rules.

Blank checkboxes are NOT inspection findings or customer feedback.
DocuSign tabs, signing, provider trust, and completion remain disabled.
"""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.lib import colors

from .installation_attestation_pdf_4942 import (
    _validated_manifest, SIGNATURE_ANCHOR, DATE_ANCHOR,
)
from .installation_attestation_manifest_4941 import (
    build_installation_signing_manifest,
)


INSPECTION_ITEMS = (
    "I inspected the installation identified above.",
    "The Project Scope of Work was completed in a professional manner.",
    "The Technician delivered quality service.",
    "The Technician removed debris, leaving a clean job site.",
    "The Customer was satisfied with the result.",
)

SURVEY_ITEMS = (
    "Did we clean up after our work?",
    "Were we professional?",
    "Would you refer us to a friend?",
)

INSPECTION_IDS = tuple(f"inspection_{i}" for i in range(1, 6))
SURVEY_IDS = tuple(f"survey_{i}" for i in range(1, 4))

NAVY = colors.HexColor("#142B3B")
TEAL = colors.HexColor("#087F75")
RED = colors.HexColor("#B33434")
GRAY = colors.HexColor("#D7E3E7")


@dataclass(frozen=True)
class InspectionActionAssessment:
    corrective_action_items: tuple
    unanswered_inspection_items: tuple
    survey_answered_count: int
    inspection_review_ready: bool
    customer_satisfaction_required_for_completion: bool = False
    provider_authenticated: bool = False
    project_completion_authorized: bool = False


def assess_inspection_answers(*, inspection, survey):
    """Assess answers only; never certify or complete a project.

    Customer survey answers must come from an independently captured
    customer-feedback workflow, not manager-attributed assertions.
    """
    if type(inspection) is not dict or type(survey) is not dict:
        raise ValidationError("Inspection and survey answer maps required.")
    if set(inspection) != set(INSPECTION_IDS):
        raise ValidationError("Exactly five inspection answers required.")
    if set(survey) != set(SURVEY_IDS):
        raise ValidationError("Exactly three survey answer fields required.")

    allowed = {"YES", "NO", None}
    if any(type(value) is not str and value is not None
           for value in (*inspection.values(), *survey.values())):
        raise ValidationError("Invalid answer type.")
    if any(value not in allowed
           for value in (*inspection.values(), *survey.values())):
        raise ValidationError("Only YES, NO, or unanswered is permitted.")

    negatives = tuple(
        key for key in INSPECTION_IDS if inspection[key] == "NO"
    )
    unanswered = tuple(
        key for key in INSPECTION_IDS if inspection[key] is None
    )
    return InspectionActionAssessment(
        corrective_action_items=negatives,
        unanswered_inspection_items=unanswered,
        survey_answered_count=sum(
            survey[key] is not None for key in SURVEY_IDS
        ),
        inspection_review_ready=not negatives and not unanswered,
    )


@dataclass(frozen=True)
class UnsignedInspectionForm:
    pdf: bytes
    pdf_sha256: str
    project_id: str
    approved_msr_id: str
    status: str = "UNSIGNED_BLANK_INSPECTION_FORM"
    inspection_responses_captured: bool = False
    customer_feedback_verified: bool = False
    docusign_tabs_configured: bool = False
    provider_authenticated: bool = False
    trusted_installation_evidence: bool = False
    final_receipt_issuance_authorized: bool = False
    completion_authorized: bool = False


def _write_wrapped(pdf, content, x, y, width=496, size=9, leading=13):
    lines = simpleSplit(content, "Helvetica", size, width)
    pdf.setFont("Helvetica", size)
    pdf.setFillColor(NAVY)
    for line in lines:
        pdf.drawString(x, y, line)
        y -= leading
    return y


def _checkbox(pdf, x, y):
    pdf.setStrokeColor(NAVY)
    pdf.rect(x, y - 3, 9, 9, fill=0, stroke=1)


def _answer_row(pdf, number, statement, y, *, with_number=True):
    x = 57
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(NAVY)

    prefix = f"{number}.  " if with_number else ""
    lines = simpleSplit(prefix + statement, "Helvetica", 9, 353)
    for index, line in enumerate(lines):
        pdf.drawString(x, y - 12 * index, line)

    _checkbox(pdf, 426, y)
    pdf.drawString(439, y, "Yes")
    _checkbox(pdf, 488, y)
    pdf.drawString(501, y, "No")
    return y - max(26, 12 * len(lines) + 12)


def render_unsigned_inspection_form(*, actor, project_id):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Offline inspection form rendering disabled.")

    manifest = build_installation_signing_manifest(
        actor=actor, project_id=project_id
    )
    _validated_manifest(manifest)

    stream = BytesIO()
    pdf = canvas.Canvas(
        stream, pagesize=letter, pageCompression=0, invariant=1
    )
    pdf.setTitle("GECC Installation Inspection Attestation")
    pdf.setAuthor("Green Energy Contracting Corporation")

    pdf.setFillColor(NAVY)
    pdf.rect(0, 682, 612, 110, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(45, 752, "Green Energy Contracting Corporation")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(45, 727, "Installation Inspection Attestation")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(45, 704, "INTERNAL - UNSIGNED - NOT RELEASED")

    metadata = (
        ("Project ID", manifest.project_id),
        ("Approved MSR / Version",
         f"{manifest.approved_msr_id} / {manifest.approved_msr_version}"),
        ("Installation source evidence ID", manifest.source_evidence_id),
        ("Source PDF SHA-256", manifest.source_pdf_sha256),
        ("Attestation preparation fingerprint",
         manifest.attestation_binding_sha256),
    )

    y = 662
    for label, value in metadata:
        pdf.setFillColor(NAVY)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(46, y, label)
        pdf.setFont("Helvetica", 8)
        lines = simpleSplit(str(value), "Helvetica", 8, 515)
        for index, line in enumerate(lines):
            pdf.drawString(46, y - 12 - 10 * index, line)
        y -= 29 + max(0, len(lines) - 1) * 10

    y -= 4
    pdf.setFont("Helvetica-Bold", 11)
    pdf.setFillColor(TEAL)
    pdf.drawString(46, y, "INSTALLATION MANAGER INSPECTION REPORT")
    y -= 18
    y = _write_wrapped(
        pdf,
        "After personally inspecting the installation, record a finding "
        "for each item.",
        46, y, size=8.5
    )
    y -= 10

    top = y + 15
    for index, statement in enumerate(INSPECTION_ITEMS, 1):
        y = _answer_row(pdf, index, statement, y)
        if index < 5:
            pdf.setStrokeColor(GRAY)
            pdf.line(55, y + 12, 557, y + 12)
    pdf.setStrokeColor(TEAL)
    pdf.roundRect(46, y + 9, 520, top - y - 3, 6, fill=0, stroke=1)

    y -= 17
    pdf.setFont("Helvetica-Bold", 11)
    pdf.setFillColor(RED)
    pdf.drawString(46, y, "CUSTOMER SATISFACTION SURVEY")
    y -= 13
    y = _write_wrapped(
        pdf,
        "Optional customer-reported feedback; leave unanswered if not obtained.",
        46, y, size=8
    )
    y -= 8
    survey_top = y + 13

    for index, question in enumerate(SURVEY_ITEMS, 1):
        y = _answer_row(pdf, index, question, y, with_number=False)
        if index < 3:
            pdf.setStrokeColor(GRAY)
            pdf.line(55, y + 12, 557, y + 12)
    pdf.setStrokeColor(RED)
    pdf.roundRect(
        46, y + 9, 520, survey_top - y - 2, 6, fill=0, stroke=1
    )

    y -= 14
    y = _write_wrapped(
        pdf,
        "I certify that I personally inspected the installation identified "
        "above and that the findings recorded on this document accurately "
        "reflect my observations.",
        46, y, size=8.5
    )
    y -= 4
    y = _write_wrapped(
        pdf, "Installation Manager: " + manifest.signer_name,
        46, y, size=8
    )
    y = _write_wrapped(
        pdf, "Signer email: " + manifest.signer_email,
        46, y, size=8
    )

    box_bottom = y - 60
    if box_bottom < 48:
        raise ValidationError("Inspection form exceeds one-page layout.")

    pdf.setStrokeColor(TEAL)
    pdf.roundRect(
        46, box_bottom, 520, 60, 6, fill=0, stroke=1
    )
    pdf.setFont("Helvetica-Bold", 8)
    pdf.setFillColor(NAVY)
    pdf.drawString(
        57, box_bottom + 41,
        "Reserved for DocuSign signature and date"
    )
    pdf.setFont("Helvetica", 8)
    pdf.drawString(57, box_bottom + 19, SIGNATURE_ANCHOR)
    pdf.drawString(320, box_bottom + 19, DATE_ANCHOR)

    pdf.showPage()
    pdf.save()
    content = stream.getvalue()

    if (
        not content.startswith(b"%PDF-")
        or not content.rstrip().endswith(b"%%EOF")
        or SIGNATURE_ANCHOR.encode() not in content
        or DATE_ANCHOR.encode() not in content
    ):
        raise ValidationError("Unsigned inspection PDF integrity failed.")

    return UnsignedInspectionForm(
        pdf=content,
        pdf_sha256=sha256(content).hexdigest(),
        project_id=manifest.project_id,
        approved_msr_id=manifest.approved_msr_id,
    )
