"""Approved-snapshot document preparation. No signature or completion assertion is made."""
import os
import hashlib
import json
from io import BytesIO
from pathlib import Path
from decimal import Decimal, InvalidOperation
from xml.sax.saxutils import escape
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, NameObject, NumberObject, TextStringObject
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from .models import Document, MSR, Project
from .equipment_catalog_snapshot import customer_equipment_description
from .services import authorize, audit, validate_snapshot
from .rules import EASTERN

RENDERER_VERSION = '0.2.0'
TEMPLATE_DIR = Path(os.getenv('GECC_PDF_TEMPLATE_DIR', str(Path(__file__).parent / 'pdf_templates')))
APPROVED_TEMPLATES = json.loads((Path(__file__).parent / 'pdf_templates' / 'manifest.json').read_text())
TEMPLATES = {
    'CONTRACT': 'GECC-Project-SOW-Agreement-Interactive.pdf',
    'INVOICE': 'GECC-HVAC-Invoice-Interactive.pdf',
    'COMPLETION_FINANCED': 'GECC-Completion-Certificate-Financed-Interactive.pdf',
    'COMPLETION_NON_FINANCED': 'GECC-Completion-Certificate-Non-Financed-Interactive.pdf',
}
SIGNATURE_FIELDS = {'customer_signature', 'gecc_signature'}

def template_path(kind):
    source = TEMPLATE_DIR / TEMPLATES[kind]
    if not source.is_file():
        raise ValidationError('The approved document template is unavailable. Contact the Comptroller.')
    synthetic = settings.ENVIRONMENT == 'development' and settings.DEBUG and os.getenv('GECC_SYNTHETIC_TEMPLATES') == '1'
    if not synthetic and hashlib.sha256(source.read_bytes()).hexdigest() != APPROVED_TEMPLATES[source.name]['sha256']:
        raise ValidationError('The document template does not match the approved version. Contact the Comptroller.')
    return source


def completion_renderer_version(kind):
    """Retain existing renderer IDs except for revised certificates."""
    if kind in ("COMPLETION_FINANCED", "COMPLETION_NON_FINANCED"):
        return "0.2.2"
    if kind in ("CONTRACT", "INVOICE"):
        return "0.2.3"
    return RENDERER_VERSION


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def money(value):
    return f'{Decimal(value):,.2f}'

def field_values(kind, record, prepared_at):
    s = record.snapshot
    common = {'project_code': record.project.code, 'msr_version': f'{record.number}.0', 'customer_printed_name': s['customer'], 'project_address': s['project_location']}
    if kind == 'INVOICE':
        values = {**common, 'customer_name':s['customer'], 'invoice_date':prepared_at.astimezone(EASTERN).date().isoformat(), 'invoice_number':f'{record.project.code}-V{record.number}', 'customer_phone':s.get('customer_phone',''), 'customer_email':s.get('customer_email',''), 'line_1_description':'Approved scope, equipment and materials - see attached detail', 'line_1_amount':money(s['base_price']), 'subtotal':money(Decimal(s['base_price'])-Decimal(s['discount'])), 'sales_tax':money(s['tax']), 'other_charges':'0.00', 'invoice_total':money(s['total_price']), 'payment_option':'/A' if s['payment_option']=='50_PERCENT_DEPOSIT' else '/B'}
        if Decimal(s['discount']):
            values.update(line_2_description='Approved discount', line_2_amount='-'+money(s['discount']))
        return values
    if kind == 'CONTRACT':
        return {**common, 'customer_name':s['customer'], 'payment_option':'50% deposit / 50% balance' if s['payment_option']=='50_PERCENT_DEPOSIT' else '100% on completion', 'financing_type':'Financed' if s['financing_type']=='FINANCED' else 'Non-financed'}
    return {**common, 'project_city':s.get('project_city',''), 'project_state':s.get('project_state',''), 'project_zip':s.get('project_zip','')}

def format_customer_equipment_line(item):
    """Render detached equipment details without modifying the snapshot."""
    if type(item) is not dict:
        raise ValueError("Equipment line must be an object.")
    quantity = item.get("quantity")
    if set(item) == {"description", "quantity"}:
        # Legacy MSRs store validated quantities as decimal strings.
        # Never rewrite approved historical snapshots.
        try:
            legacy_quantity = Decimal(str(quantity))
            if (
                type(quantity) not in (str, int)
                or not legacy_quantity.is_finite()
                or legacy_quantity <= 0
                or legacy_quantity > 100000
            ):
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("Invalid legacy equipment quantity.")
    elif type(quantity) is not int or not 1 <= quantity <= 999:
        raise ValueError("Equipment quantity must be from 1 to 999.")
    return (
        f"{customer_equipment_description(item)} "
        f"(quantity {quantity})"
    )


def appendix(record, kind, prepared_at, signing_test=False):
    """Full snapshot details flow over pages, without truncating scope or item lists."""
    stream = BytesIO()
    styles = getSampleStyleSheet()
    styles['BodyText'].leading = 14
    styles['Heading3'].keepWithNext = True
    s = record.snapshot
    content = [Paragraph('Approved project detail', styles['Title']), Paragraph(f"Project {escape(record.project.code)} | MSR {record.number}.0", styles['Heading2']), Paragraph('SANDBOX SIGNING TEST - fictional workflow only; no actual work, agreement, payment or lender authorization.' if signing_test else 'UNSIGNED PREPARATION COPY - signing workflow has not started.', styles['BodyText']), Spacer(1,12)]
    if kind.startswith('COMPLETION_') and not signing_test:
        content += [Paragraph('Do not sign until work is complete. This preparation copy does not establish completion, payment verification, or lender funding authorization.', styles['BodyText']), Spacer(1,12)]
    def text(label, value):
        # Reject unsupported glyphs rather than silently rendering missing characters.
        try:
            value.encode('cp1252')
        except UnicodeEncodeError:
            raise ValidationError('Document preparation currently requires Western European characters. An embedded multilingual font adapter is needed for this record.')
        content.append(Paragraph(escape(label), styles['Heading3']))
        content.append(Paragraph(escape(value).replace('\n','<br/>'), styles['BodyText']))
    for label, key in [('Customer','customer'),('Contact','contact'),('Billing address','billing_address'),('Installation address','project_location'),('Installation city','project_city'),('Installation state','project_state'),('Installation ZIP','project_zip'),('Customer phone','customer_phone'),('Customer email','customer_email'),('Scope of work','scope')]:
        value = s.get(key,'')
        if value:
            text(label, value)
    for label,key in [('Equipment','equipment'),('Materials','materials')]:
        if key == 'equipment':
            items = [format_customer_equipment_line(item) for item in s[key]]
        else:
            items = [f"{item['description']} (quantity {item['quantity']})" for item in s[key]]
        text(label, '\n'.join(items) or 'None specified in the approved record.')
    rows = [['Approved price','USD'],['Base price',money(s['base_price'])],['Discount',('0.00' if Decimal(str(s['discount'])) == 0 else '-'+money(s['discount']))],['Sales tax',money(s['tax'])],['Total price',money(s['total_price'])]]
    table = Table(rows, colWidths=[350,130]);table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eee7')),('GRID',(0,0),(-1,-1),.5,colors.HexColor('#c9d4cb')),('ALIGN',(1,1),(1,-1),'RIGHT'),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]));content += [Spacer(1,16),table]
    text('Payment option','50% deposit / 50% at completion' if s['payment_option']=='50_PERCENT_DEPOSIT' else '100% at completion')
    text('Payment terms',s['payment_terms'])
    if s.get('financing_type'):
        text('Financing','Financed' if s['financing_type']=='FINANCED' else 'Non-financed')
    if s.get('commercial_notes'):
        text('Commercial notes',s['commercial_notes'])
    text('Installation eligibility','Five Eastern calendar days after the verified customer Contract signature, and after any later applicable cancellation deadline. Verified Contract signature, required payment verification or an approved exception, and other installation prerequisites still apply. The customer Invoice signature is not a pre-installation requirement. No eligibility date has been calculated in this preparation copy.')
    def footer(c, doc):
        c.setFont('Helvetica',8);c.setFillColor(colors.HexColor('#647a6b'));c.drawString(48,25,f'{record.project.code} | MSR {record.number}.0 | Approved detail');c.drawRightString(564,25,f'Page {doc.page}')
    SimpleDocTemplate(stream,pagesize=(612,792),leftMargin=48,rightMargin=48,topMargin=48,bottomMargin=48).build(content,onFirstPage=footer,onLaterPages=footer)
    return PdfReader(BytesIO(stream.getvalue()))


def refresh_completion_identity(writer, kind):
    """Update new certificate copies without changing approved templates."""
    if kind not in ("COMPLETION_FINANCED", "COMPLETION_NON_FINANCED"):
        return

    from io import BytesIO
    from pypdf import PdfReader
    from pypdf.generic import ContentStream, NameObject, TextStringObject
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics

    # Reposition the printed title and project label without modifying
    # the approved PDF template or any previously generated document.
    title = "COMPLETION CERTIFICATE"
    subtitle = (
        "FINANCED PROJECT" if kind == "COMPLETION_FINANCED"
        else "NON-FINANCED PROJECT"
    )
    measured = {}

    def capture_header(text, cm, tm, font_dict, font_size):
        label = str(text).strip()
        if label in (title, subtitle):
            measured.setdefault(label, []).append(
                (float(tm[5]), float(font_size))
            )

    old_header = (
        "20906 Frederick Road Ste A 1010",
        "Germantown, MD 20876",
        "Email: geccmd@gmail.com",
    )
    old_warning = (
        "PLEASE DO NOT SIGN THIS DOCUMENT UNTIL THE WORK IS COMPLETE"
    )
    targets = (*old_header, old_warning, title, subtitle)
    counts = {value: 0 for value in targets}

    page = writer.pages[0]
    page.extract_text(visitor_text=capture_header)
    for label in (title, subtitle):
        locations = measured.get(label, [])
        if len(locations) != 1:
            raise ValueError(
                "STOP: Certificate label location not unique: " + label
            )
        y, size = locations[0]
        if not (650 < y < 790 and 7 <= size <= 25):
            raise ValueError(
                "STOP: Unexpected certificate label geometry: "
                + repr((label, y, size))
            )

    stream = ContentStream(page.get_contents(), writer)

    for operands, operator in stream.operations:
        if operator == b"Tj" and operands:
            value = str(operands[0])
            if value in counts:
                counts[value] += 1
                operands[0] = TextStringObject("")
        elif operator == b"TJ" and operands:
            for index, item in enumerate(operands[0]):
                if isinstance(item, (str, TextStringObject)):
                    value = str(item)
                    if value in counts:
                        counts[value] += 1
                        operands[0][index] = TextStringObject("")

    if any(count != 1 for count in counts.values()):
        raise ValueError(
            "STOP: Template printed text was not uniquely found: "
            + repr(counts)
        )

    page[NameObject("/Contents")] = writer._add_object(stream)

    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    company = "Green Energy Contracting Corporation"
    contact = (
        "Office Phone: 888-977-1711    "
        "Email: care@gecc.cloud"
    )

    if pdfmetrics.stringWidth(contact, "Helvetica", 10.0) > 365:
        raise ValueError("STOP: Contact line too wide.")

    # Center within the space between the two original logo areas.
    # The logos remain in the original approved template.
    center_x = (113.0 + 459.0) / 2.0
    available_width = 459.0 - 113.0
    if pdfmetrics.stringWidth(contact, "Helvetica", 10.0) > available_width - 12:
        raise ValueError("STOP: Contact line overlaps the logo areas.")

    overlay = BytesIO()
    drawing = canvas.Canvas(overlay, pagesize=(width, height))
    drawing.setFillColorRGB(0, 0, 0)
    drawing.setFont("Helvetica-Bold", measured[title][0][1])
    drawing.drawCentredString(center_x, measured[title][0][0], title)
    drawing.setFont("Helvetica", 12)
    drawing.drawCentredString(center_x, 736, company)
    drawing.setFont("Helvetica", 10)
    drawing.drawCentredString(center_x, 718, contact)
    drawing.setFont("Helvetica-Bold", measured[subtitle][0][1])
    drawing.drawCentredString(
        center_x, measured[subtitle][0][0], subtitle
    )
    drawing.save()
    overlay.seek(0)
    page.merge_page(PdfReader(overlay).pages[0])




def refresh_other_document_identity(writer, kind):
    """Clean headers for newly prepared Contracts and Invoices only."""
    if kind not in ("CONTRACT", "INVOICE"):
        return

    from PIL import Image, ImageDraw
    from pypdf.generic import ContentStream, NameObject, TextStringObject
    from reportlab.pdfbase.pdfmetrics import stringWidth

    page = writer.pages[0]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    if (width, height) != (612.0, 792.0):
        raise ValueError("STOP: Unexpected document dimensions.")

    company = "Green Energy Contracting Corporation"
    contact = "Office Phone: 888-977-1711    Email: care@gecc.cloud"
    old_text = (
        ("HVAC INVOICE",
         "20906 Frederick Road Ste A 1010",
         "Germantown, MD 20876",
         "Email: geccmd@gmail.com",
         "Phone: 702-782-3863")
        if kind == "INVOICE" else ("Email: geccmd@gmail.com",)
    )

    counts = {value: 0 for value in old_text}
    stream = ContentStream(page.get_contents(), writer)
    for operands, operation in stream.operations:
        if operation == b"Tj" and operands:
            value = str(operands[0])
            if value in counts:
                counts[value] += 1
                operands[0] = TextStringObject("")
        elif operation == b"TJ" and operands:
            for index, item in enumerate(operands[0]):
                if isinstance(item, (str, TextStringObject)):
                    value = str(item)
                    if value in counts:
                        counts[value] += 1
                        operands[0][index] = TextStringObject("")

    if any(count != 1 for count in counts.values()):
        raise ValueError("STOP: Original header text changed: " + repr(counts))
    page[NameObject("/Contents")] = writer._add_object(stream)

    if kind == "CONTRACT":
        if len(page.images) != 1:
            raise ValueError("STOP: Unexpected Agreement banner images.")
        embedded = page.images[0]
        picture = Image.open(BytesIO(embedded.data)).convert("RGB")
        if picture.size != (908, 131):
            raise ValueError("STOP: Unexpected Agreement banner dimensions.")

        # Remove the old central artwork from the image itself.
        # Preserve both original logo regions.
        left = round((125.0 - 50.4) * picture.width / 511.2)
        right = round((432.0 - 50.4) * picture.width / 511.2)
        if not (120 <= left <= 145 and 670 <= right <= 690):
            raise ValueError("STOP: Unexpected Agreement image boundaries.")

        clean = picture.copy()
        ImageDraw.Draw(clean).rectangle(
            (left, 0, right, picture.height - 1),
            fill=(255, 255, 255)
        )
        for box in (
            (0, 0, left, picture.height),
            (right + 1, 0, picture.width, picture.height)
        ):
            if clean.crop(box).tobytes() != picture.crop(box).tobytes():
                raise ValueError("STOP: Protected logo pixels changed.")
        embedded.replace(clean)

        center_x = 288.5
        lines = (
            ("PROJECT SCOPE OF WORK AGREEMENT", "Helvetica-Bold", 11.0, 746),
            (company, "Helvetica", 11.0, 727),
            (contact, "Helvetica", 8.2, 708),
        )
        safe_left, safe_right = 130.0, 427.0
    else:
        center_x = 286.0
        lines = (
            ("HVAC INVOICE", "Helvetica-Bold", 15.0, 752),
            (company, "Helvetica", 12.0, 734),
            (contact, "Helvetica", 10.0, 711),
        )
        safe_left, safe_right = 113.0, 459.0

    overlay = BytesIO()
    drawing = canvas.Canvas(overlay, pagesize=(width, height))
    drawing.setFillColorRGB(0, 0, 0)
    for label, font, size, y in lines:
        measured = stringWidth(label, font, size)
        if center_x - measured / 2 < safe_left or center_x + measured / 2 > safe_right:
            raise ValueError("STOP: Header overlaps protected logo area.")
        drawing.setFont(font, size)
        drawing.drawCentredString(center_x, y, label)
    drawing.save()
    overlay.seek(0)
    page.merge_page(PdfReader(overlay).pages[0])


def render_pdf(kind, record, prepared_at, sandbox_review=None, release_context=None, signing_test=False):
    if signing_test and (not release_context or sandbox_review):
        raise ValidationError("Signing tests require a separate verified test review.")
    review = sandbox_review or (release_context['review'] if release_context else None)
    source = template_path(kind)
    reader = PdfReader(source)
    writer = PdfWriter();writer.clone_document_from_reader(reader)
    refresh_completion_identity(writer, kind)
    refresh_other_document_identity(writer, kind)
    fields = writer.get_fields() or {}
    if not SIGNATURE_FIELDS.issubset(fields) or any(fields[name].get('/FT')!='/Sig' for name in SIGNATURE_FIELDS):
        raise ValidationError('The template lacks required native signature fields.')
    values = field_values(kind, record, prepared_at)
    if review:
        values.update(customer_printed_name=review['customer']['name'],
                      gecc_representative_name=review['gecc']['name'],
                      gecc_role=review['gecc']['role'].replace('_', ' ').title())
        if 'gecc_substitute_reason' in fields:
            values['gecc_substitute_reason'] = review['substitute_reason']
    if release_context:
        evidence = release_context['evidence']
        if kind == 'CONTRACT':
            values['cancellation_deadline'] = evidence['deadline']
        if kind.startswith('COMPLETION_'):
            values['completion_date'] = evidence['completion_date']
            if 'completion_exceptions' in fields:
                values['completion_exceptions'] = 'Exceptions reviewed and resolved; see verification reference.'
    if set(values)-set(fields):
        raise ValidationError('The document template and field mapping disagree.')
    # Font sizes adapt within a readable range. Full values remain in the attached detail.
    for page in writer.pages:
        for ref in page.get('/Annots',[]):
            widget = ref.get_object();field = widget.get('/Parent',widget).get_object();name = field.get('/T')
            if name in values and field.get('/FT') == '/Tx':
                value = values[name]
                try:
                    value.encode('cp1252')
                except UnicodeEncodeError:
                    raise ValidationError('Document field contains unsupported characters.')
                width = float(widget['/Rect'][2]-widget['/Rect'][0])-8
                fontsize = 9
                if stringWidth(value,'Helvetica',fontsize)>width:
                    fontsize = 8
                if stringWidth(value,'Helvetica',fontsize)>width:
                    if review and name in {'customer_printed_name', 'gecc_representative_name'}:
                        raise ValidationError('Reviewed signer name does not fit the approved signature field. Template review is required.')
                    values[name] = 'See detail' if width >= 45 else 'Detail'
                writer.update_page_form_field_values(page,{name:(values[name],'/Helv',fontsize)},auto_regenerate=False)
    writer.update_page_form_field_values(None,values,auto_regenerate=False)
    # Lock populated commercial fields while leaving signatures/actor/date fields interactive.
    for ref in writer.root_object['/AcroForm']['/Fields']:
        field = ref.get_object()
        if field.get('/T') in values:
            field[NameObject('/Ff')] = NumberObject(int(field.get('/Ff',0)) | 1)
    # A preparation watermark keeps certificates from being mistaken for completed attestations.
    for page in writer.pages:
        overlay=BytesIO();c=canvas.Canvas(overlay,pagesize=(float(page.mediabox.width),float(page.mediabox.height)))
        c.saveState();c.translate(306,396);c.rotate(35);c.setFillColor(colors.Color(.28,.40,.32,alpha=.13));c.setFont('Helvetica-Bold',27);c.drawCentredString(0,0,'SANDBOX SIGNING TEST' if signing_test else 'SANDBOX TEST - DO NOT SIGN' if sandbox_review else 'UNSIGNED RELEASE REVIEW' if release_context else 'UNSIGNED PREPARATION COPY');c.restoreState();c.save()
        page.merge_page(PdfReader(BytesIO(overlay.getvalue())).pages[0])
    for page in appendix(record,kind,prepared_at,signing_test=signing_test).pages:
        writer.add_page(page)
    if review:
        summary = BytesIO()
        styles = getSampleStyleSheet()
        rows = [Paragraph('Sandbox signing test review' if signing_test else 'Sandbox routing review' if sandbox_review else 'Release routing and verification review', styles['Title']),
                Paragraph('SANDBOX SIGNING TEST. Signatures simulate the workflow only. This is not an actual agreement, work-completion verification, payment instruction or lender authorization.' if signing_test else 'TEST ONLY. Not approved for sending or signing. No work completion or cancellation deadline has been verified.' if sandbox_review else 'UNSIGNED RELEASE REVIEW. Manual verification is recorded below. Sending remains disabled.', styles['BodyText'])]
        for label, value in [('Customer signer', review['customer']['name']),
                             ('Customer email', review['customer']['email']),
                             ('GECC signer', review['gecc']['name']),
                             ('GECC email', review['gecc']['email']),
                             ('GECC role', review['gecc']['role'].replace('_', ' ')),
                             ('Substitution reason', review['substitute_reason'] or 'Not applicable')]:
            rows += [Spacer(1, 10), Paragraph(escape(label), styles['Heading3']), Paragraph(escape(value), styles['BodyText'])]
        if release_context:
            for value in evidence.values():
                if isinstance(value, str):
                    try:value.encode('cp1252')
                    except UnicodeEncodeError:raise ValidationError('Verification text requires Western European characters until multilingual rendering is implemented.')
            for label, value in [('Verification method', 'Manual attestation'), ('Evidence reference', evidence['source_reference']), ('Verification note', evidence['verification_note']), ('Exact cancellation deadline', evidence.get('deadline', 'Not applicable to this package')), ('Verified completion date', evidence.get('completion_date', 'Not applicable to this package'))]:
                rows += [Spacer(1,10), Paragraph(escape(label), styles['Heading3']), Paragraph(escape(value), styles['BodyText'])]
        SimpleDocTemplate(summary, pagesize=(612, 792)).build(rows)
        for page in PdfReader(BytesIO(summary.getvalue())).pages:
            writer.add_page(page)
    if signing_test:
        # Repeat a visible test banner on every page, including flowing appendix pages.
        for page in writer.pages:
            overlay=BytesIO();c=canvas.Canvas(overlay,pagesize=(float(page.mediabox.width),float(page.mediabox.height)))
            c.setFillColor(colors.HexColor('#8d2f1b'));c.setFont('Helvetica-Bold',10)
            c.drawString(36,float(page.mediabox.height)-20,'SANDBOX SIGNING TEST - NO ACTUAL AGREEMENT OR WORK VERIFICATION')
            c.save();page.merge_page(PdfReader(BytesIO(overlay.getvalue())).pages[0])
    writer.add_metadata({'/Title':f'GECC {kind} | {record.project.code} | MSR {record.number}.0','/Subject':'Fictional sandbox signing test; no actual agreement or work verification' if signing_test else 'Unsigned preparation copy from an approved immutable MSR','/GECCMSR':str(record.id),'/GECCSnapshotSHA256':canonical_hash(record.snapshot)})
    stream=BytesIO();writer.write(stream);content=stream.getvalue()
    verify = PdfReader(BytesIO(content));actual=verify.get_fields() or {}
    for name,value in values.items():
        if str(actual[name].get('/V','')) != value:
            raise ValidationError(f'Field verification failed: {name}')
    for name in SIGNATURE_FIELDS:
        if actual[name].get('/FT')!='/Sig' or actual[name].get('/V'):
            raise ValidationError('Signature fields must remain unsigned.')
    return content,values,hashlib.sha256(source.read_bytes()).hexdigest()

@transaction.atomic
def generate(actor, msr_id, kind):
    if kind not in TEMPLATES:
        raise ValidationError('Choose a supported document type.')
    reference = MSR.objects.get(pk=msr_id)
    project = Project.objects.select_for_update().get(pk=reference.project_id)
    authorize(actor,project,approval=True)
    record = MSR.objects.select_related('project').get(pk=msr_id)
    if record.status!='APPROVED' or project.current_approved_id!=record.id or project.state=='CANCELLED':
        raise ValidationError('Generate documents only from the current approved version of an active project.')
    validate_snapshot(record.snapshot,complete=True)
    financing=record.snapshot.get('financing_type')
    if kind!='INVOICE' and financing not in {'FINANCED','NON_FINANCED'}:
        raise ValidationError('This approved version does not specify financing. Create and approve a revision first.')
    if kind=='COMPLETION_FINANCED' and financing!='FINANCED' or kind=='COMPLETION_NON_FINANCED' and financing!='NON_FINANCED':
        raise ValidationError('Certificate type must match the approved financing selection.')
    template_hash=hashlib.sha256(template_path(kind).read_bytes()).hexdigest()
    existing=Document.objects.filter(msr=record,kind=kind,template_sha256=template_hash,renderer_version=completion_renderer_version(kind)).first()
    if existing:
        return existing,False
    created_at=timezone.now()
    content,values,template_hash=render_pdf(kind,record,created_at)
    if len(content)>5*1024*1024:
        raise ValidationError('The generated document exceeds the preparation size limit.')
    document=Document.objects.create(msr=record,kind=kind,created_by=actor,filename=f'{project.code}-V{record.number}-{kind}.pdf',template_sha256=template_hash,snapshot_sha256=canonical_hash(record.snapshot),pdf_sha256=hashlib.sha256(content).hexdigest(),renderer_version=completion_renderer_version(kind),values=values,content=content)
    audit(actor,'document.generated',project.id,{'document_id':str(document.id),'msr_id':str(record.id),'version':record.number,'kind':kind,'template_sha256':template_hash,'snapshot_sha256':document.snapshot_sha256,'pdf_sha256':document.pdf_sha256,'status':'PREPARATION'})
    return document,True
