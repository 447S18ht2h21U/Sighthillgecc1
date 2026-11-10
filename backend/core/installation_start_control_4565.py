"""Read-only operational installation-start safety assessment.

No installation start may be authorized until independently trusted
equipment evidence and start authorization are implemented and verified.
"""
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .installation_database_schedule_readiness import assess_database_schedule
from .installation_eligibility import ensure_installation_eligible
from .expedited_contract_evidence_4566 import assess_contract_evidence
from .expedited_chain_readiness_4566 import assess_expedited_chain


def assess_installation_start(*, project, proposed_start):
    if timezone.is_naive(proposed_start):
        raise ValidationError("Timezone-aware start time required.")

    reasons = []
    schedule = assess_database_schedule(
        project_id=project.pk,
        installation_starts_at=proposed_start,
    )

    if schedule.schedule_verified is not True:
        reasons.extend(schedule.blockers)

    if proposed_start > timezone.now():
        reasons.append("Installation cannot begin at a future time.")

    commercial_ready = False
    try:
        commercial_ready = ensure_installation_eligible(project) is True
    except ValidationError as exc:
        reasons.append(str(exc.detail))

    # No operational trusted-equipment issuer or start-authorization
    # workflow has yet been approved. Never interpret previews or
    # review-candidate flags as sufficient proof.
    reasons.append(
        "Trusted physical-equipment verification and operational "
        "installation-start authorization are not yet implemented."
    )

    contract = assess_contract_evidence(project)
    expedited = assess_expedited_chain(project)

    return {
        "customer_contract_signature_recorded": (
            contract.customer_contract_signature_recorded
        ),
        "generated_contract_integrity_verified": (
            contract.generated_contract_integrity_verified
        ),
        "customer_initials_verified": False,
        "signed_expedited_document_verified": False,
        "expedited_chain_reviewed": expedited["expedited_chain_reviewed"],
        "project_id": str(project.pk),
        "schedule_verified": schedule.schedule_verified is True,
        "commercial_ready": commercial_ready,
        "trusted_equipment_verified": False,
        "expedited_authorized": False,
        "installation_authorized": False,
        "installation_started": False,
        "blockers": list(dict.fromkeys(reasons)),
    }
