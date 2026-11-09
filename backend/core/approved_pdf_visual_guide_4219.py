"""Development-only coordinate guides for verified approved PDFs.

Never alters originals or releases customer documents.
"""
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from .approved_pdf_reference_integrity_4217 import (
    APPROVED_PDFS,
    verify_reference,
)


def build_visual_guide(reference_dir, kind):
    """Overlay a numbered 50-point grid on a new PDF copy."""
    reference_dir = Path(reference_dir)
    verified = verify_reference(reference_dir, kind)

    source = reference_dir / verified.filename
    reader = PdfReader(BytesIO(source.read_bytes()), strict=True)
    writer = PdfWriter()

    for number, original_page in enumerate(reader.pages, 1):
        page = writer.add_page(original_page)
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        stream = BytesIO()
        guide = canvas.Canvas(stream, pagesize=(width, height))

        guide.saveState()
        guide.setStrokeColorRGB(0.10, 0.45, 0.65)
        guide.setFillColorRGB(0.10, 0.35, 0.55)
        guide.setLineWidth(0.3)
        guide.setFont("Helvetica", 6)

        for x in range(0, int(width) + 1, 50):
            guide.line(x, 0, x, height)
            if 8 <= x <= width - 15:
                guide.drawString(x + 2, 8, f"x={x}")

        for y in range(0, int(height) + 1, 50):
            guide.line(0, y, width, y)
            if 8 <= y <= height - 15:
                guide.drawString(4, y + 2, f"y={y}")

        guide.restoreState()

        guide.saveState()
        guide.setFillColorRGB(0.65, 0.08, 0.08)
        guide.setFont("Helvetica-Bold", 9)
        guide.drawCentredString(
            width / 2,
            height - 18,
            "DEVELOPMENT GUIDE - NOT FOR CUSTOMER USE",
        )
        guide.setFont("Helvetica", 7)
        guide.drawCentredString(
            width / 2,
            20,
            f"{kind} | Page {number} | PDF coordinates from bottom-left",
        )
        guide.restoreState()
        guide.save()

        stream.seek(0)
        overlay = PdfReader(stream, strict=True)
        page.merge_page(overlay.pages[0])

    writer.add_metadata({
        "/Title": f"VERIDIAN placement guide - {kind}",
        "/Subject": "Development-only PDF coordinate review",
    })

    result = BytesIO()
    writer.write(result)
    content = result.getvalue()

    if len(PdfReader(BytesIO(content)).pages) != verified.page_count:
        raise ValueError("Guide page count mismatch.")

    return content


def save_all_guides(reference_dir, output_dir):
    """Verify originals, then create six separate development guides."""
    reference_dir = Path(reference_dir)
    output_dir = Path(output_dir)

    if output_dir.exists():
        raise ValueError("Guide destination already exists.")

    before = {
        filename: sha256((reference_dir / filename).read_bytes()).hexdigest()
        for filename, _, _ in APPROVED_PDFS.values()
    }

    generated = {
        kind: build_visual_guide(reference_dir, kind)
        for kind in APPROVED_PDFS
    }

    after = {
        filename: sha256((reference_dir / filename).read_bytes()).hexdigest()
        for filename, _, _ in APPROVED_PDFS.values()
    }

    if before != after:
        raise ValueError("Approved PDF original changed.")

    output_dir.mkdir(parents=True, exist_ok=False)

    result = {}
    for kind, content in generated.items():
        destination = output_dir / f"{kind}-PLACEMENT-GUIDE.pdf"
        destination.write_bytes(content)
        if sha256(destination.read_bytes()).digest() != sha256(content).digest():
            raise ValueError("Guide write verification failed.")
        result[kind] = destination

    return result