"""Fictional pre-sign commercial release, separate from post-sign evidence.

Never asserts a cancellation deadline, customer signature, payment, or
installation eligibility. No provider network operations or sending.
"""

import base64
import hashlib

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import sandbox
from .documents import canonical_hash, render_pdf
from .models import (
    Project,
    ReleaseApproval,
    ReleasePackage,
    SigningPlan,
)
from .services import authorize, audit
from .signing import required_text


PURPOSE = 'FICTIONAL_PRE_SIGN_COMMERCIAL'
VERSION = 'fictional-commercial-presign-0.1'


def binding(plan):
    return canonical_hash({
        'purpose': PURPOSE,
        'version': VERSION,
        'plan_digest': plan.digest,
        'msr_snapshot': canonical_hash(plan.msr.snapshot),
    })


@transaction.atomic
def prepare(actor, plan_id):
    plan = SigningPlan.objects.select_related(
        'msr__project'
    ).get(pk=plan_id)

    Project.objects.select_for_update().get(pk=plan.msr.project_id)

    plan = SigningPlan.objects.select_related(
        'msr__project'
    ).get(pk=plan_id)

    authorize(actor, plan.msr.project, approval=True)

    if not actor.is_active or plan.group != 'COMMERCIAL':
        raise PermissionDenied('Authorized commercial review preparer required.')

    review = sandbox.current(plan)

    if [d.get('kind') for d in review['documents']] != ['CONTRACT', 'INVOICE']:
        raise ValidationError('Current Contract and Invoice review required.')

    bound = binding(plan)

    existing = ReleasePackage.objects.filter(
        plan=plan,
        payload__purpose=PURPOSE,
        payload__binding_digest=bound,
    ).first()

    if existing:
        validate(existing)
        return existing, False

    from django.utils import timezone

    entries = []
    total = 0

    for source in review['documents']:
        content, values, template_hash = render_pdf(
            source['kind'],
            plan.msr,
            timezone.now(),
            pre_sign_commercial_review=review,
        )

        if template_hash != source['template_sha256']:
            raise ValidationError('Reviewed document template changed.')

        total += len(content)
        if total > sandbox.MAX_PDF_BYTES:
            raise ValidationError('Pre-sign commercial package exceeds size limit.')

        entries.append({
            'kind': source['kind'],
            'filename': (
                f'{plan.msr.project.code}-V{plan.msr.number}-'
                f'{source["kind"]}-FICTIONAL-PRESIGN.pdf'
            ),
            'pdf_sha256': hashlib.sha256(content).hexdigest(),
            'template_sha256': template_hash,
            'values': values,
            'documentBase64': base64.b64encode(content).decode('ascii'),
        })

    payload = {
        'purpose': PURPOSE,
        'version': VERSION,
        'binding_digest': bound,
        'plan_digest': plan.digest,
        'documents': entries,
        'sandbox_only': True,
        'cancellation_deadline_verified': False,
        'send_available': False,
    }

    package = ReleasePackage.objects.create(
        plan=plan,
        created_by=actor,
        payload=payload,
        digest=canonical_hash(payload),
    )

    audit(
        actor,
        'commercial_presign.package_prepared',
        plan.msr.project_id,
        {
            'package_id': str(package.id),
            'plan_id': str(plan.id),
            'digest': package.digest,
            'sandbox_only': True,
        },
    )
    return package, True


def validate(package, check_current=True):
    payload = package.payload

    if (
        payload.get('purpose') != PURPOSE
        or payload.get('version') != VERSION
        or payload.get('sandbox_only') is not True
        or payload.get('cancellation_deadline_verified') is not False
        or payload.get('send_available') is not False
        or canonical_hash(payload) != package.digest
    ):
        raise ValidationError('Fictional pre-sign package integrity failed.')

    if package.plan.group != 'COMMERCIAL':
        raise ValidationError('Pre-sign package must be commercial.')

    entries = payload.get('documents')
    if (
        not isinstance(entries, list)
        or [d.get('kind') for d in entries] != ['CONTRACT', 'INVOICE']
    ):
        raise ValidationError('Pre-sign documents must be Contract and Invoice.')

    for entry in entries:
        try:
            content = base64.b64decode(
                entry['documentBase64'], validate=True
            )
        except (KeyError, TypeError, ValueError):
            raise ValidationError('Pre-sign PDF encoding invalid.') from None

        if (
            not content.startswith(b'%PDF-')
            or hashlib.sha256(content).hexdigest() != entry.get('pdf_sha256')
        ):
            raise ValidationError('Pre-sign PDF integrity failed.')

    if check_current:
        plan = SigningPlan.objects.select_related(
            'msr__project'
        ).get(pk=package.plan_id)
        sandbox.current(plan)

        if (
            payload.get('plan_digest') != plan.digest
            or payload.get('binding_digest') != binding(plan)
        ):
            raise ValidationError('Pre-sign package is no longer current.')


@transaction.atomic
def decide(actor, package_id, data):
    reference = ReleasePackage.objects.select_related(
        'plan__msr__project'
    ).get(pk=package_id)

    Project.objects.select_for_update().get(
        pk=reference.plan.msr.project_id
    )

    package = ReleasePackage.objects.select_related(
        'plan__msr__project'
    ).get(pk=package_id)

    authorize(actor, package.plan.msr.project, approval=True)

    if not actor.is_active:
        raise PermissionDenied('Inactive release reviewer.')

    if (
        not isinstance(data, dict)
        or data.get('decision') not in {'APPROVED', 'REVOKED'}
    ):
        raise ValidationError('Choose approve or revoke.')

    decision = data['decision']
    note = required_text(data, 'note', 2000)

    if decision == 'APPROVED':
        validate(package)

        if actor.id == package.created_by_id:
            raise PermissionDenied(
                'A different authorized person must approve the exact documents.'
            )

        if data.get('documents_and_evidence_reviewed') is not True:
            raise ValidationError(
                'Confirm independent review of the documents, recipients, '
                'routing, and fictional pre-sign classification.'
            )

    previous = package.decisions.order_by(
        '-created_at', '-id'
    ).first()

    if (
        previous
        and previous.created_by_id == actor.id
        and previous.decision == decision
        and previous.note == note
    ):
        return previous, False

    digest = canonical_hash({
        'package_digest': package.digest,
        'actor': str(actor.id),
        'decision': decision,
        'note': note,
    })

    result = ReleaseApproval.objects.create(
        package=package,
        created_by=actor,
        decision=decision,
        note=note,
        package_digest=package.digest,
        digest=digest,
    )

    audit(
        actor,
        'commercial_presign.decision_recorded',
        package.plan.msr.project_id,
        {
            'package_id': str(package.id),
            'decision_id': str(result.id),
            'decision': decision,
            'digest': digest,
        },
    )
    return result, True


def status(package):
    try:
        validate(package)
    except (ValidationError, PermissionDenied) as exc:
        return {
            'status': 'BLOCKED',
            'send_available': False,
            'blockers': [str(exc.detail)],
        }

    latest = package.decisions.order_by(
        '-created_at', '-id'
    ).first()

    if latest:
        expected = canonical_hash({
            'package_digest': package.digest,
            'actor': str(latest.created_by_id),
            'decision': latest.decision,
            'note': latest.note,
        })

        if (
            latest.digest != expected
            or latest.package_digest != package.digest
        ):
            return {
                'status': 'BLOCKED',
                'send_available': False,
                'blockers': ['Release approval integrity failed.'],
            }

        reviewer = latest.created_by
        try:
            authorize(reviewer, package.plan.msr.project, approval=True)
        except PermissionDenied:
            return {
                'status': 'BLOCKED',
                'send_available': False,
                'blockers': ['Release reviewer no longer authorized.'],
            }

        if (
            not reviewer.is_active
            or (
                latest.decision == 'APPROVED'
                and reviewer.id == package.created_by_id
            )
        ):
            return {
                'status': 'BLOCKED',
                'send_available': False,
                'blockers': ['Independent approval is invalid.'],
            }

    state = (
        'REVIEW_REQUIRED' if latest is None
        else 'APPROVED' if latest.decision == 'APPROVED'
        else 'REVOKED'
    )

    return {
        'status': state,
        'send_available': False,
        'blockers': [
            'Fictional sandbox sending remains disabled pending '
            'separate authorization and activation.'
        ],
    }
