"""Docusign routing review foundation. No provider calls or signature assertions."""
import hashlib
from io import BytesIO
from uuid import UUID
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from pypdf import PdfReader
from rest_framework.exceptions import ValidationError
from .models import Document, MSR, Project, Role, SigningPlan, User
from .services import authorize, audit
from .documents import canonical_hash

GROUPS = {'COMMERCIAL': ['CONTRACT', 'INVOICE'],
          'COMPLETION_FINANCED': ['COMPLETION_FINANCED'],
          'COMPLETION_NON_FINANCED': ['COMPLETION_NON_FINANCED']}


def candidates(project, group):
    users = User.objects.filter(is_active=True).exclude(email='')
    if group == 'COMMERCIAL':
        return users.filter(Q(pk=project.reviewer_id, role=Role.SALES_MANAGER) | Q(role=Role.COMPTROLLER))
    return users.filter(role__in=[Role.INSTALLATION_MANAGER, Role.COMPTROLLER])


def field_positions(content):
    """Read widget rectangles, convert PDF bottom-left to Docusign top-left (72 DPI)."""
    reader = PdfReader(BytesIO(content))
    positions = {}
    for number, page in enumerate(reader.pages, 1):
        if page.rotation or list(page.cropbox) != list(page.mediabox) or float(page.get('/UserUnit', 1)) != 1:
            raise ValidationError('Signing review requires unrotated standard-size PDF pages.')
        for ref in page.get('/Annots', []):
            widget = ref.get_object()
            if widget.get('/Subtype') != '/Widget':
                continue
            field = widget.get('/Parent', widget).get_object()
            name = field.get('/T')
            if name not in {'customer_signature', 'gecc_signature', 'customer_signed_date', 'gecc_signed_date', 'customer_printed_name', 'gecc_representative_name', 'customer_payment_initials'}:
                continue
            if name in positions:
                raise ValidationError('Duplicate signing widget mapping requires template review.')
            left, bottom, right, top = map(float, widget['/Rect'])
            if left < float(page.mediabox.left) or right > float(page.mediabox.right) or bottom < float(page.mediabox.bottom) or top > float(page.mediabox.top):
                raise ValidationError('Signing field lies outside its page.')
            positions[name] = {'pageNumber': str(number), 'xPosition': str(round(left-float(page.mediabox.left))), 'yPosition': str(round(float(page.mediabox.top)-top))}
    required = {'customer_signature', 'gecc_signature', 'customer_signed_date', 'gecc_signed_date', 'customer_printed_name', 'gecc_representative_name'}
    if not required.issubset(positions):
        raise ValidationError('The PDF lacks required signature, printed-name, or date widgets.')
    return positions


def envelope_preview(documents, customer, gecc, commercial):
    """Metadata preview only: preparation PDFs are deliberately absent from this payload."""
    recipients = []
    for recipient_id, identity, prefix in [('1', customer, 'customer'), ('2', gecc, 'gecc')]:
        tabs = {'signHereTabs': [], 'dateSignedTabs': [], 'fullNameTabs': []}
        for document_id, document in enumerate(documents, 1):
            positions = field_positions(bytes(document.content))
            for tab_type, field in [('signHereTabs', prefix+'_signature'), ('dateSignedTabs', prefix+'_signed_date'), ('fullNameTabs', 'customer_printed_name' if prefix == 'customer' else 'gecc_representative_name')]:
                tab = {**positions[field], 'documentId': str(document_id), 'recipientId': recipient_id, 'tabLabel': field}
                if tab_type == 'signHereTabs':
                    tab['optional'] = 'false'
                tabs[tab_type].append(tab)
            if prefix == 'customer' and 'customer_payment_initials' in positions:
                tabs.setdefault('initialHereTabs', []).append({**positions['customer_payment_initials'], 'documentId': str(document_id), 'recipientId': recipient_id, 'tabLabel': 'customer_payment_initials', 'optional': 'false'})
        recipients.append({'recipientId': recipient_id, 'routingOrder': '1' if (prefix == 'customer') == commercial else '2', 'name': identity['name'], 'email': identity['email'], 'tabs': tabs})
    return {'status': 'created', 'recipients': {'signers': recipients},
            'notification': {'useAccountDefaults': 'false', 'expirations': {'expireEnabled': 'true', 'expireAfter': '75', 'expireWarn': '5'}},
            'documents': [{'documentId': str(i), 'name': d.filename, 'fileExtension': 'pdf', 'transformPdfFields': 'false'} for i, d in enumerate(documents, 1)]}


def required_text(data, key, maximum=250):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError({key: f'A nonempty value of at most {maximum} characters is required.'})
    return value.strip()


@transaction.atomic
def prepare(actor, msr_id, data):
    if not isinstance(data, dict):
        raise ValidationError('Signing review must be a JSON object.')
    reference = MSR.objects.get(pk=msr_id)
    project = Project.objects.select_for_update().get(pk=reference.project_id)
    authorize(actor, project, approval=True)
    record = MSR.objects.get(pk=msr_id)
    if record.status != 'APPROVED' or project.current_approved_id != record.id or project.state == 'CANCELLED':
        raise ValidationError('Signing review requires the current approved version of an active project.')
    group = data.get('group')
    if not isinstance(group, str) or group not in GROUPS:
        raise ValidationError('Choose a supported signing workflow.')
    if group.startswith('COMPLETION_') and group != 'COMPLETION_'+record.snapshot.get('financing_type', ''):
        raise ValidationError('Completion workflow must match the approved financing selection.')
    customer = {'name': required_text(data, 'customer_name'), 'email': required_text(data, 'customer_email', 254)}
    authority = required_text(data, 'authority_note', 2000)
    try:
        validate_email(customer['email'])
        signer_id = UUID(str(data.get('gecc_signer')))
    except (DjangoValidationError, ValueError, TypeError):
        raise ValidationError('Choose valid customer email and GECC signer identifiers.')
    signer = candidates(project, group).filter(pk=signer_id).first()
    if not signer:
        raise ValidationError('The selected GECC signer is unavailable or has an incompatible role.')
    gecc = {'user_id': str(signer.id), 'name': signer.get_full_name().strip(), 'email': signer.email, 'role': signer.role}
    if not gecc['name']:
        raise ValidationError('The GECC signer must have a full name in their account profile.')
    try:
        validate_email(gecc['email'])
    except DjangoValidationError:
        raise ValidationError('The GECC signer account requires a valid email address.')
    if customer['email'].casefold() == gecc['email'].casefold():
        raise ValidationError('Customer and GECC must use separate signing email addresses.')
    reason = ''
    if group != 'COMMERCIAL' and signer.role == Role.COMPTROLLER:
        reason = required_text(data, 'substitute_reason', 2000)
    docs = []
    for kind in GROUPS[group]:
        doc = Document.objects.filter(msr=record, kind=kind).order_by('-created_at').first()
        if not doc:
            raise ValidationError(f'Prepare the {kind.lower().replace("_", " ")} PDF before reviewing its signing workflow.')
        if doc.pdf_sha256 != hashlib.sha256(bytes(doc.content)).hexdigest() or doc.snapshot_sha256 != canonical_hash(record.snapshot):
            raise ValidationError('Source document integrity verification failed.')
        docs.append(doc)
    review = {'schema_version': 1, 'msr_id': str(record.id), 'msr_version': record.number,
              'snapshot_sha256': canonical_hash(record.snapshot), 'group': group,
              'customer': customer, 'gecc': gecc, 'authority_note': authority,
              'substitute_reason': reason,
              'documents': [{'id': str(d.id), 'kind': d.kind, 'pdf_sha256': d.pdf_sha256, 'template_sha256': d.template_sha256} for d in docs],
              'envelope_preview': envelope_preview(docs, customer, gecc, group == 'COMMERCIAL')}
    digest = canonical_hash(review)
    existing = SigningPlan.objects.filter(msr=record, group=group, digest=digest).first()
    if existing:
        return existing, False
    plan = SigningPlan.objects.create(msr=record, group=group, created_by=actor, review=review, digest=digest)
    audit(actor, 'signing.review_prepared', project.id, {'plan_id': str(plan.id), 'digest': digest, 'review': review})
    return plan, True


def status(plan):
    project = plan.msr.project
    blockers = ['Docusign account connection is pending.', 'Signer-ready PDFs and release approval are pending.', 'Provider status reconciliation and signed-document retention are pending.']
    if canonical_hash(plan.review) != plan.digest:
        blockers.insert(0, 'Signing review integrity verification failed.')
    stale = project.current_approved_id != plan.msr_id
    replaced = SigningPlan.objects.filter(msr=plan.msr, group=plan.group, created_at__gt=plan.created_at).exists()
    cancelled = project.state == 'CANCELLED'
    signer = User.objects.filter(pk=plan.review['gecc']['user_id'], is_active=True).first()
    identity = plan.review['gecc']
    changed = not signer or signer.role != identity['role'] or signer.email != identity['email'] or signer.get_full_name().strip() != identity['name']
    if changed:
        blockers.insert(0, 'GECC signer account changed; prepare a new review.')
    if stale:
        blockers.insert(0, 'A newer approved MSR superseded this signing review.')
    if replaced:
        blockers.insert(0, 'A newer recipient review superseded this signing review.')
    if cancelled:
        blockers.insert(0, 'Project is cancelled.')
    if plan.group != 'COMMERCIAL':
        blockers.append('Work completion must be verified before certificate signing.')
    return {'status': 'CANCELLED' if cancelled else 'SUPERSEDED' if stale or replaced else 'REVIEW_REQUIRED' if changed else 'PREPARED',
            'provider_status': None, 'send_available': False, 'release_blockers': blockers,
            'expiration_days_after_first_send': 75, 'installation_wait_calendar_days': 5}
