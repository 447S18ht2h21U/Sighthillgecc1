"""Manual verification and independent release review. No send authorization/API."""
import base64
import hashlib
from datetime import date
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied, ValidationError
from .documents import canonical_hash, render_pdf
from .models import MSR, Project, ProjectEvidence, ReleaseApproval, ReleasePackage, Role, SigningPlan
from .rules import EASTERN
from .services import authorize, audit
from .sandbox import current, MAX_PDF_BYTES
from .signing import required_text

KINDS = {'CANCELLATION_DEADLINE', 'WORK_COMPLETION'}
VERSION = 'release-review-0.1'


def lock_record(msr_id):
    reference = MSR.objects.get(pk=msr_id)
    Project.objects.select_for_update().get(pk=reference.project_id)
    record = MSR.objects.select_related('project').get(pk=msr_id)
    if not settings.DEBUG:
        raise ValidationError('Release review is available only in development; production identity is pending.')
    if record.status != 'APPROVED' or record.project.current_approved_id != record.id or record.project.state == 'CANCELLED':
        raise ValidationError('Verification requires the current approved version of an active project.')
    return record


def latest(record, kind):
    return ProjectEvidence.objects.filter(msr=record,kind=kind).order_by('-created_at','-id').first()


@transaction.atomic
def record_evidence(actor, msr_id, data):
    record=lock_record(msr_id)
    if not actor.is_active or actor.role != Role.COMPTROLLER:
        raise PermissionDenied('Only the Comptroller records manual verification evidence in this slice.')
    if not isinstance(data,dict) or not isinstance(data.get('kind'),str) or data.get('kind') not in KINDS:
        raise ValidationError('Choose cancellation-deadline or work-completion evidence.')
    kind=data['kind']
    payload={'source_reference':required_text(data,'source_reference',2000),
             'verification_note':required_text(data,'verification_note',2000),
             'snapshot_sha256':canonical_hash(record.snapshot),'method':'MANUAL_ATTESTATION',
             'verified':data.get('verified') is True}
    if not isinstance(data.get('verified'),bool):
        raise ValidationError('Choose explicit verification or withdrawal.')
    if payload['verified']:
        if kind=='CANCELLATION_DEADLINE':
            raw=required_text(data,'deadline',80)
            try: deadline=parse_datetime(raw)
            except (ValueError,TypeError): deadline=None
            if not deadline or timezone.is_naive(deadline):
                raise ValidationError('Enter an exact cancellation deadline including its UTC offset.')
            if data.get('notice_and_applicability_checked') is not True:
                raise ValidationError('Confirm review of notice delivery and applicable cancellation rights.')
            payload.update(deadline=deadline.astimezone(EASTERN).isoformat(),notice_and_applicability_checked=True)
        else:
            try: completed=date.fromisoformat(required_text(data,'completion_date',10))
            except ValueError: raise ValidationError('Enter a valid completion date.')
            if completed>timezone.now().astimezone(EASTERN).date():
                raise ValidationError('Work completion cannot be in the future.')
            for flag in ['work_verified','permits_inspections_checked','exceptions_resolved']:
                if data.get(flag) is not True:
                    raise ValidationError('Work, permits/inspection applicability, and exceptions must be verified before release review.')
                payload[flag]=True
            payload.update(completion_date=completed.isoformat(),
                           substitute_reason=required_text(data,'substitute_reason',2000))
    digest=canonical_hash(payload)
    existing=latest(record,kind)
    if existing and existing.digest==digest:
        return existing,False
    evidence=ProjectEvidence.objects.create(msr=record,kind=kind,created_by=actor,data=payload,digest=digest)
    audit(actor,'release.evidence_recorded',record.project_id,{'evidence_id':str(evidence.id),'kind':kind,'digest':digest,'verified':payload['verified']})
    return evidence,True


def evidence_for(plan):
    kind='CANCELLATION_DEADLINE' if plan.group=='COMMERCIAL' else 'WORK_COMPLETION'
    evidence=latest(plan.msr,kind)
    if (not evidence or evidence.data.get('verified') is not True or canonical_hash(evidence.data)!=evidence.digest
            or evidence.data['snapshot_sha256']!=canonical_hash(plan.msr.snapshot)):
        raise ValidationError('Current verified '+kind.lower().replace('_',' ')+' evidence is required.')
    return evidence


def binding(plan,evidence):
    return canonical_hash({'plan_digest':plan.digest,'evidence_id':str(evidence.id),'evidence_digest':evidence.digest,'version':VERSION})


@transaction.atomic
def prepare_package(actor,plan_id):
    plan=SigningPlan.objects.select_related('msr__project').get(pk=plan_id)
    lock_record(plan.msr_id)
    plan=SigningPlan.objects.select_related('msr__project').get(pk=plan_id)
    authorize(actor,plan.msr.project,approval=True)
    if not actor.is_active:raise PermissionDenied('Inactive release preparer.')
    review=current(plan);evidence=evidence_for(plan);bound=binding(plan,evidence)
    existing=ReleasePackage.objects.filter(plan=plan,payload__binding_digest=bound).first()
    if existing:
        validate_package(existing);return existing,False
    entries=[];total=0
    for source in review['documents']:
        content,values,template_digest=render_pdf(source['kind'],plan.msr,timezone.now(),
            release_context={'review':review,'evidence':evidence.data})
        if template_digest!=source['template_sha256']:
            raise ValidationError('Reviewed template changed. Prepare a new recipient review.')
        total+=len(content)
        if total>MAX_PDF_BYTES: raise ValidationError('Release review package exceeds its size limit.')
        entries.append({'kind':source['kind'],'filename':f'{plan.msr.project.code}-V{plan.msr.number}-{source["kind"]}-RELEASE-REVIEW.pdf',
                        'pdf_sha256':hashlib.sha256(content).hexdigest(),'template_sha256':template_digest,
                        'values':values,'documentBase64':base64.b64encode(content).decode()})
    payload={'purpose':'UNSIGNED_RELEASE_REVIEW','version':VERSION,'binding_digest':bound,'plan_digest':plan.digest,
             'evidence_id':str(evidence.id),'evidence_digest':evidence.digest,'documents':entries}
    package=ReleasePackage.objects.create(plan=plan,created_by=actor,payload=payload,digest=canonical_hash(payload))
    audit(actor,'release.package_prepared',plan.msr.project_id,{'package_id':str(package.id),'digest':package.digest,
          'plan_id':str(plan.id),'evidence_id':str(evidence.id),'pdf_hashes':[d['pdf_sha256'] for d in entries]})
    return package,True


def validate_package(package,check_current=True):
    if canonical_hash(package.payload)!=package.digest:
        raise ValidationError('Release package integrity verification failed.')
    for entry in package.payload['documents']:
        if hashlib.sha256(base64.b64decode(entry['documentBase64'],validate=True)).hexdigest()!=entry['pdf_sha256']:
            raise ValidationError('Release PDF integrity verification failed.')
    if check_current:
        package.plan = SigningPlan.objects.select_related('msr__project').get(pk=package.plan_id)
        current(package.plan)
        evidence=evidence_for(package.plan)
        if package.payload['binding_digest']!=binding(package.plan,evidence):
            raise ValidationError('Verification evidence changed; prepare and approve a new release package.')


@transaction.atomic
def decide(actor,package_id,data):
    package=ReleasePackage.objects.select_related('plan__msr__project').get(pk=package_id)
    lock_record(package.plan.msr_id)
    package=ReleasePackage.objects.select_related('plan__msr__project').get(pk=package_id)
    authorize(actor,package.plan.msr.project,approval=True)
    if not actor.is_active:raise PermissionDenied('Inactive release reviewer.')
    if not isinstance(data,dict) or not isinstance(data.get('decision'),str) or data.get('decision') not in {'APPROVED','REVOKED'}:
        raise ValidationError('Choose approve or revoke.')
    decision=data['decision'];note=required_text(data,'note',2000)
    if decision=='APPROVED':
        validate_package(package)
        evidence=evidence_for(package.plan)
        if actor.id in {package.created_by_id,evidence.created_by_id}:
            raise PermissionDenied('A different authorized reviewer must approve the evidence and release documents.')
        if data.get('documents_and_evidence_reviewed') is not True:
            raise ValidationError('Confirm review of the exact documents, recipients, evidence and routing.')
    previous=package.decisions.order_by('-created_at','-id').first()
    if previous and previous.decision==decision and previous.created_by_id==actor.id and previous.note==note:
        return previous,False
    digest=canonical_hash({'package_digest':package.digest,'actor':str(actor.id),'decision':decision,'note':note})
    result=ReleaseApproval.objects.create(package=package,created_by=actor,decision=decision,note=note,package_digest=package.digest,digest=digest)
    audit(actor,'release.decision_recorded',package.plan.msr.project_id,{'decision_id':str(result.id),'package_id':str(package.id),'decision':decision,'digest':digest})
    return result,True


def status(package):
    try:validate_package(package)
    except ValidationError as exc:return {'status':'BLOCKED','send_available':False,'blockers':[str(exc.detail)]}
    decision=package.decisions.order_by('-created_at','-id').first()
    if decision:
        digest=canonical_hash({'package_digest':package.digest,'actor':str(decision.created_by_id),'decision':decision.decision,'note':decision.note})
        if digest!=decision.digest or decision.package_digest!=package.digest:
            return {'status':'BLOCKED','send_available':False,'blockers':['Release approval integrity verification failed.']}
        reviewer=decision.created_by
        try:authorize(reviewer,package.plan.msr.project,approval=True)
        except PermissionDenied:return {'status':'BLOCKED','send_available':False,'blockers':['Release reviewer is no longer authorized.']}
        if not reviewer.is_active:return {'status':'BLOCKED','send_available':False,'blockers':['Release reviewer is inactive.']}
    state='REVIEW_REQUIRED' if not decision else 'APPROVED' if decision.decision=='APPROVED' else 'REVOKED'
    return {'status':state,'send_available':False,'blockers':['Sending, provider lifecycle reconciliation, signed retention and production identity remain pending.']}


def describe(package):
    return {'id':str(package.id),'digest':package.digest,'created_by':str(package.created_by_id),
            'evidence_id':package.payload['evidence_id'],'release':status(package),
            'documents':[{'kind':e['kind'],'filename':e['filename'],'pdf_sha256':e['pdf_sha256'],
                          'download_url':f'/api/release-packages/{package.id}/documents/{i}/'} for i,e in enumerate(package.payload['documents'])],
            'decisions':[{'id':str(d.id),'decision':d.decision,'note':d.note,'created_by':str(d.created_by_id),'created_at':d.created_at.isoformat()} for d in package.decisions.order_by('-created_at','-id')]}
