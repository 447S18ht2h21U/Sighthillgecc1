"""Approved-snapshot document preparation. No signature or completion assertion is made."""
import os
import hashlib
import json
from io import BytesIO
from pathlib import Path
from decimal import Decimal
from xml.sax.saxutils import escape
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, NumberObject
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from .models import Document, MSR, Project
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
    synthetic = settings.DEBUG and os.getenv('GECC_SYNTHETIC_TEMPLATES') == '1'
    if not synthetic and hashlib.sha256(source.read_bytes()).hexdigest() != APPROVED_TEMPLATES[source.name]['sha256']:
        raise ValidationError('The document template does not match the approved version. Contact the Comptroller.')
    return source

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

def appendix(record, kind, prepared_at):
    """Full snapshot details flow over pages, without truncating scope or item lists."""
    stream = BytesIO()
    styles = getSampleStyleSheet()
    styles['BodyText'].leading = 14
    styles['Heading3'].keepWithNext = True
    s = record.snapshot
    content = [Paragraph('Approved project detail', styles['Title']), Paragraph(f"Project {escape(record.project.code)} | MSR {record.number}.0", styles['Heading2']), Paragraph('UNSIGNED PREPARATION COPY - signing workflow has not started.', styles['BodyText']), Spacer(1,12)]
    if kind.startswith('COMPLETION_'):
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
        text(label, '\n'.join(f"{item['description']} (quantity {item['quantity']})" for item in s[key]) or 'None specified in the approved record.')
    rows = [['Approved price','USD'],['Base price',money(s['base_price'])],['Discount','-'+money(s['discount'])],['Sales tax',money(s['tax'])],['Total price',money(s['total_price'])]]
    table = Table(rows, colWidths=[350,130]);table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eee7')),('GRID',(0,0),(-1,-1),.5,colors.HexColor('#c9d4cb')),('ALIGN',(1,1),(1,-1),'RIGHT'),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]));content += [Spacer(1,16),table]
    text('Payment option','50% deposit / 50% at completion' if s['payment_option']=='50_PERCENT_DEPOSIT' else '100% at completion')
    text('Payment terms',s['payment_terms'])
    if s.get('financing_type'):
        text('Financing','Financed' if s['financing_type']=='FINANCED' else 'Non-financed')
    if s.get('commercial_notes'):
        text('Commercial notes',s['commercial_notes'])
    text('Installation eligibility','Five Eastern calendar days after the later customer contract/invoice signature, and after any later applicable cancellation deadline. Required signatures and verified deposit also apply. No eligibility date has been calculated in this preparation copy.')
    def footer(c, doc):
        c.setFont('Helvetica',8);c.setFillColor(colors.HexColor('#647a6b'));c.drawString(48,25,f'{record.project.code} | MSR {record.number}.0 | Approved detail');c.drawRightString(564,25,f'Page {doc.page}')
    SimpleDocTemplate(stream,pagesize=(612,792),leftMargin=48,rightMargin=48,topMargin=48,bottomMargin=48).build(content,onFirstPage=footer,onLaterPages=footer)
    return PdfReader(BytesIO(stream.getvalue()))

def render_pdf(kind, record, prepared_at, sandbox_review=None):
    source = template_path(kind)
    reader = PdfReader(source)
    writer = PdfWriter();writer.clone_document_from_reader(reader)
    fields = writer.get_fields() or {}
    if not SIGNATURE_FIELDS.issubset(fields) or any(fields[name].get('/FT')!='/Sig' for name in SIGNATURE_FIELDS):
        raise ValidationError('The template lacks required native signature fields.')
    values = field_values(kind, record, prepared_at)
    if sandbox_review:
        values.update(customer_printed_name=sandbox_review['customer']['name'],
                      gecc_representative_name=sandbox_review['gecc']['name'],
                      gecc_role=sandbox_review['gecc']['role'].replace('_', ' ').title())
        if 'gecc_substitute_reason' in fields:
            values['gecc_substitute_reason'] = sandbox_review['substitute_reason']
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
                    if sandbox_review and name in {'customer_printed_name', 'gecc_representative_name'}:
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
        c.saveState();c.translate(306,396);c.rotate(35);c.setFillColor(colors.Color(.28,.40,.32,alpha=.13));c.setFont('Helvetica-Bold',27);c.drawCentredString(0,0,'SANDBOX TEST - DO NOT SIGN' if sandbox_review else 'UNSIGNED PREPARATION COPY');c.restoreState();c.save()
        page.merge_page(PdfReader(BytesIO(overlay.getvalue())).pages[0])
    for page in appendix(record,kind,prepared_at).pages:
        writer.add_page(page)
    if sandbox_review:
        summary = BytesIO()
        styles = getSampleStyleSheet()
        rows = [Paragraph('Sandbox routing review', styles['Title']),
                Paragraph('TEST ONLY. Not approved for sending or signing. No work completion or cancellation deadline has been verified.', styles['BodyText'])]
        for label, value in [('Customer signer', sandbox_review['customer']['name']),
                             ('Customer email', sandbox_review['customer']['email']),
                             ('GECC signer', sandbox_review['gecc']['name']),
                             ('GECC email', sandbox_review['gecc']['email']),
                             ('GECC role', sandbox_review['gecc']['role'].replace('_', ' ')),
                             ('Substitution reason', sandbox_review['substitute_reason'] or 'Not applicable')]:
            rows += [Spacer(1, 10), Paragraph(escape(label), styles['Heading3']), Paragraph(escape(value), styles['BodyText'])]
        SimpleDocTemplate(summary, pagesize=(612, 792)).build(rows)
        for page in PdfReader(BytesIO(summary.getvalue())).pages:
            writer.add_page(page)
    writer.add_metadata({'/Title':f'GECC {kind} | {record.project.code} | MSR {record.number}.0','/Subject':'Unsigned preparation copy from an approved immutable MSR','/GECCMSR':str(record.id),'/GECCSnapshotSHA256':canonical_hash(record.snapshot)})
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
    existing=Document.objects.filter(msr=record,kind=kind,template_sha256=template_hash,renderer_version=RENDERER_VERSION).first()
    if existing:
        return existing,False
    created_at=timezone.now()
    content,values,template_hash=render_pdf(kind,record,created_at)
    if len(content)>5*1024*1024:
        raise ValidationError('The generated document exceeds the preparation size limit.')
    document=Document.objects.create(msr=record,kind=kind,created_by=actor,filename=f'{project.code}-V{record.number}-{kind}.pdf',template_sha256=template_hash,snapshot_sha256=canonical_hash(record.snapshot),pdf_sha256=hashlib.sha256(content).hexdigest(),renderer_version=RENDERER_VERSION,values=values,content=content)
    audit(actor,'document.generated',project.id,{'document_id':str(document.id),'msr_id':str(record.id),'version':record.number,'kind':kind,'template_sha256':template_hash,'snapshot_sha256':document.snapshot_sha256,'pdf_sha256':document.pdf_sha256,'status':'PREPARATION'})
    return document,True
