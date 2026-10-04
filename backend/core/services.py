import copy
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from django.db import transaction, connection
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import AuditHead, AuditEvent, Outbox, LocalCounter, MSR, Project, Role
from .rules import PAYMENT_OPTIONS, EASTERN
EDITORS = {Role.SALES_ASSOCIATE, Role.SALES_MANAGER, Role.COMPTROLLER}
APPROVERS = {Role.SALES_MANAGER, Role.COMPTROLLER}

def permitted(user, project):
    return user.role == Role.COMPTROLLER or (user.role == Role.SALES_ASSOCIATE and project.sales_associate_id == user.id) or (user.role == Role.SALES_MANAGER and project.reviewer_id == user.id)

def authorize(user, project, approval=False):
    if not permitted(user, project) or user.role not in (APPROVERS if approval else EDITORS):
        raise PermissionDenied('You do not have permission for this project.')

def audit(actor, action, entity_id, payload):
    # Caller holds an atomic transaction; a singleton lock serializes the hash chain.
    head = AuditHead.objects.select_for_update().get(pk=1)
    sequence = head.sequence + 1
    previous = head.digest
    body = {'sequence': sequence, 'actor': str(actor.id), 'action': action, 'entity_id': str(entity_id), 'payload': payload, 'previous_hash': previous}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    event = AuditEvent.objects.create(sequence=sequence, actor=actor, action=action, entity_id=entity_id, payload=payload, previous_hash=previous, digest=digest)
    head.sequence, head.digest = sequence, digest
    head.save()
    Outbox.objects.create(event=event, topic=action, payload={'audit_id': str(event.id), 'entity_id': str(entity_id)})
    return event

def next_code(initials):
    if not re.fullmatch('[A-Z]{1,8}', initials):
        raise ValidationError('Sales Associate initials must be 1–8 uppercase letters.')
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute("SELECT nextval('gecc_project_number')")
            number = cursor.fetchone()[0]
    else:
        counter = LocalCounter.objects.select_for_update().get(pk=1)
        counter.value += 1
        counter.save()
        number = counter.value
    return f'{number}-{initials}-{timezone.now().astimezone(EASTERN).date().isoformat()}'

SNAPSHOT_FIELDS = {'customer', 'contact', 'billing_address', 'project_location', 'scope', 'equipment', 'materials', 'base_price', 'discount', 'tax', 'total_price', 'payment_option', 'payment_terms', 'commercial_notes'}
def validate_snapshot(data, complete=False):
    if not isinstance(data, dict) or set(data) - SNAPSHOT_FIELDS:
        raise ValidationError('Invalid or unknown commercial fields.')
    result = copy.deepcopy(data)
    for key in ('customer', 'contact', 'billing_address', 'project_location', 'scope', 'payment_terms', 'commercial_notes'):
        if key in result and (not isinstance(result[key], str) or len(result[key]) > 10000):
            raise ValidationError({key: 'Must be text, at most 10,000 characters.'})
    for key in ('equipment', 'materials'):
        if key in result:
            if not isinstance(result[key], list) or len(result[key]) > 100:
                raise ValidationError({key: 'Provide a list of up to 100 line items.'})
            for item in result[key]:
                if not isinstance(item, dict) or set(item) != {'description', 'quantity'} or not isinstance(item['description'], str) or not item['description'].strip():
                    raise ValidationError({key: 'Each item requires a description and quantity.'})
                try:
                    quantity = Decimal(str(item['quantity']))
                    if not quantity.is_finite() or quantity <= 0 or quantity > 100000:
                        raise ValueError()
                except (InvalidOperation, ValueError):
                    raise ValidationError({key: 'Quantity must be positive and finite.'})
                item['quantity'] = str(quantity)
    for key in ('base_price', 'discount', 'tax', 'total_price'):
        if key in result:
            try:
                value = Decimal(str(result[key]))
                if not value.is_finite() or value < 0 or value > Decimal('999999999.99') or value != value.quantize(Decimal('.01')):
                    raise ValueError()
            except (InvalidOperation, ValueError):
                raise ValidationError({key: 'Provide nonnegative USD with at most two decimal places.'})
            result[key] = format(value, '.2f')
    if 'payment_option' in result and result['payment_option'] not in PAYMENT_OPTIONS:
        raise ValidationError({'payment_option': 'Choose 50% deposit or 100% at completion.'})
    if complete:
        required = SNAPSHOT_FIELDS - {'commercial_notes', 'contact'}
        missing = [key for key in required if key not in result or (isinstance(result[key], str) and not result[key].strip())]
        if missing:
            raise ValidationError({'required': sorted(missing)})
        expected = Decimal(result['base_price']) - Decimal(result['discount']) + Decimal(result['tax'])
        if expected != Decimal(result['total_price']) or expected <= 0:
            raise ValidationError({'total_price': 'Must equal base price minus discount plus tax and be positive.'})
    return result

@transaction.atomic
def create_project(actor, customer, location, associate, reviewer, duplicate_reason=''):
    if actor.role not in EDITORS:
        raise PermissionDenied()
    if associate.role != Role.SALES_ASSOCIATE or reviewer.role != Role.SALES_MANAGER or not associate.is_active or not reviewer.is_active:
        raise ValidationError('Choose an active Sales Associate and Sales Manager.')
    if actor.role == Role.SALES_ASSOCIATE and associate != actor:
        raise PermissionDenied('Sales Associates may create only their own projects.')
    if actor.role == Role.SALES_MANAGER and reviewer != actor:
        raise PermissionDenied('Sales Managers may create only projects they review.')
    # Serialize duplicate detection for this customer and protect archived customer race.
    customer = type(customer).objects.select_for_update().get(pk=customer.pk)
    if customer.archived:
        raise ValidationError('Customer is archived.')
    duplicates = Project.objects.filter(customer=customer, location__iexact=location.strip()).exists()
    if duplicates and not duplicate_reason.strip():
        raise ValidationError({'duplicate_warning': 'A project exists for this customer/location. Supply duplicate_reason to continue.'})
    project = Project.objects.create(code=next_code(associate.initials), customer=customer, location=location.strip(), sales_associate=associate, reviewer=reviewer)
    draft = MSR.objects.create(project=project, created_by=actor, prepared_by=actor, snapshot={'customer': customer.legal_name, 'billing_address': customer.billing_address, 'project_location': project.location, 'contact': '', 'scope': '', 'equipment': [], 'materials': [], 'base_price': '0.00', 'discount': '0.00', 'tax': '0.00', 'total_price': '0.00', 'payment_option': '50_PERCENT_DEPOSIT', 'payment_terms': '', 'commercial_notes': ''})
    project.pending = draft
    project.save()
    audit(actor, 'project.created', project.id, {'code': project.code, 'version': 1, 'duplicate_override': duplicate_reason})
    return project

@transaction.atomic
def transition(actor, msr_id, action, expected_sequence, snapshot=None, reason=''):
    # All writes lock the project first, then the version: consistent lock order.
    ref = MSR.objects.get(pk=msr_id)
    project = Project.objects.select_for_update().get(pk=ref.project_id)
    record = MSR.objects.select_for_update().get(pk=msr_id)
    authorize(actor, project, approval=action in {'approve', 'reject'})
    if project.state == 'CANCELLED' or project.pending_id != record.id:
        raise ValidationError('This is not the active draft. Approved records require a revision.')
    if type(expected_sequence) is not int or expected_sequence != record.edit_sequence:
        raise ValidationError({'conflict': 'This record changed. Refresh before making another change.'})
    if action == 'edit':
        if record.status not in {'DRAFT', 'REJECTED'}:
            raise ValidationError('Only drafts or rejected records can be edited.')
        record.snapshot = validate_snapshot(snapshot)
        record.prepared_by = actor
    elif action == 'submit':
        if record.status not in {'DRAFT', 'REJECTED'}:
            raise ValidationError('Only a draft or rejected record can be submitted.')
        record.snapshot = validate_snapshot(record.snapshot, complete=True)
        record.status = project.state = 'SUBMITTED'
        record.submitted_at = timezone.now()
    elif action in {'approve', 'reject'}:
        if record.status != 'SUBMITTED':
            raise ValidationError('Only submitted records can be reviewed.')
        if actor.id in {record.created_by_id, record.prepared_by_id}:
            raise PermissionDenied('A different authorized person must review the prepared record.')
        if action == 'reject' and not reason.strip():
            raise ValidationError('A rejection reason is required.')
        record.status = project.state = 'APPROVED' if action == 'approve' else 'REJECTED'
        if action == 'approve':
            record.approved_at, record.approved_by = timezone.now(), actor
            project.current_approved, project.pending = record, None
    else:
        raise ValidationError('Unknown transition.')
    record.edit_sequence += 1
    record.save()
    project.save()
    # Retain the exact submitted/rejected/approved contents, including prior attempts.
    audit(actor, f'msr.{action}', project.id, {'msr_id': str(record.id), 'version': record.number, 'edit_sequence': record.edit_sequence, 'reason': reason, 'snapshot': record.snapshot})
    return record

@transaction.atomic
def revise(actor, project_id, reason, expected_approved_id):
    project = Project.objects.select_for_update().get(pk=project_id)
    authorize(actor, project)
    if not reason.strip() or not project.current_approved_id or project.pending_id or project.state == 'CANCELLED':
        raise ValidationError('Revision requires an approved version, a reason, and no pending draft.')
    if str(project.current_approved_id) != expected_approved_id:
        raise ValidationError({'conflict': 'The approved version changed. Refresh first.'})
    number = (project.versions.aggregate(n=Max('number'))['n'] or 0) + 1
    draft = MSR.objects.create(project=project, number=number, source=project.current_approved, revision_reason=reason, created_by=actor, prepared_by=actor, snapshot=copy.deepcopy(project.current_approved.snapshot))
    project.pending, project.state = draft, 'REVISED'
    project.save()
    audit(actor, 'msr.revised', project.id, {'msr_id': str(draft.id), 'source': str(draft.source_id), 'version': number, 'reason': reason})
    return draft

@transaction.atomic
def change_project_state(actor, project_id, action, reason, expected_state):
    project = Project.objects.select_for_update().get(pk=project_id)
    authorize(actor, project, approval=True)
    if not reason.strip() or project.state != expected_state:
        raise ValidationError('Supply a reason and refresh the current project state.')
    before = project.state
    if action == 'cancel' and before != 'CANCELLED':
        project.state = 'CANCELLED'
    elif action == 'reopen' and before == 'CANCELLED':
        project.state = project.pending.status if project.pending_id else 'APPROVED'
        if project.pending_id and project.pending.source_id and project.pending.status == 'DRAFT':
            project.state = 'REVISED'
    else:
        raise ValidationError('Invalid project state transition.')
    project.save()
    audit(actor, f'project.{action}', project.id, {'reason':reason,'previous_state':before,'state':project.state})
    return project
