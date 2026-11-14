"""Read-only operational installation completion evidence.

Schedule completion and provisional equipment decisions are observations,
not independently authenticated installation completion or Receipt authority.
"""

from dataclasses import dataclass
from django.utils import timezone

from .post_installation_acceptance_verifier_4820 import (
    verify_post_installation_acceptance,
)
from .installation_provenance_gate_4825 import (
    assess_installation_provenance,
)
from .models import InstallationSchedule
from .installation_inspection_correlation_4818 import (
    assess_installation_inspection_candidates,
)
from .equipment_trust_verifier_4785 import verify_equipment_trust_decisions


@dataclass(frozen=True)
class InstallationCompletionEvidence:
    project_id: str
    operational_schedule_completed: bool
    provisional_equipment_decisions_verified: bool
    completed_schedule_count: int
    blockers: tuple[str, ...]
    physical_unit_count: int = 0
    verified_inspection_candidate_count: int = 0
    all_inspection_candidates_verified: bool = False
    installation_provenance_status: str = "UNVERIFIED"
    installation_source_integrity_verified: bool = False
    acceptance_candidate_verified: bool = False
    post_installation_acceptance_verified: bool = False
    trusted_installation_evidence: bool = False
    final_receipt_issuance_authorized: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def assess_installation_completion_evidence(project):
    if project is None or getattr(project, "pk", None) is None:
        raise ValueError("Persisted project required.")

    msr = getattr(project, "current_approved", None)

    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
        or project.state == "CANCELLED"
    ):
        raise ValueError("Active project and current approved MSR required.")

    schedules = list(
        InstallationSchedule.objects.filter(
            project=project,
            status=InstallationSchedule.Status.COMPLETED,
        ).order_by("pk")
    )

    valid = (
        len(schedules) == 1
        and schedules[0].completed_at is not None
        and schedules[0].cancelled_at is None
        and schedules[0].scheduled_date is not None
        and schedules[0].scheduled_date <= timezone.localdate()
    )

    blockers = []

    if not valid:
        blockers.append(
            "A consistent operational installation completion "
            "record has not been established."
        )

    provisional = False

    try:
        equipment = verify_equipment_trust_decisions(project)
        provisional = (
            equipment.project_id == str(project.pk)
            and equipment.msr_id == str(msr.pk)
            and equipment.all_approval_decisions_verified is True
            and equipment.trusted_installation_evidence is False
            and equipment.installation_authorized is False
            and equipment.receipt_issuance_authorized is False
            and equipment.completion_authorized is False
        )
    except (ValueError, TypeError, AttributeError):
        provisional = False

    if not provisional:
        blockers.append(
            "Provisional equipment decisions are incomplete "
            "or could not be independently verified."
        )

    inspection = assess_installation_inspection_candidates(project)
    if (
        inspection.project_id != str(project.pk)
        or inspection.msr_id != str(msr.pk)
        or inspection.post_installation_acceptance_verified is not False
        or inspection.trusted_installation_evidence is not False
        or inspection.final_receipt_issuance_authorized is not False
        or inspection.completion_authorized is not False
    ):
        raise ValueError("Inspection correlation authority mismatch.")
    blockers.extend(inspection.blockers)
    acceptance = verify_post_installation_acceptance(project)
    if (
        acceptance.project_id != str(project.pk)
        or acceptance.msr_id != str(msr.pk)
        or acceptance.post_installation_acceptance_verified is not False
        or acceptance.trusted_installation_evidence is not False
        or acceptance.final_receipt_issuance_authorized is not False
        or acceptance.customer_delivery_verified is not False
        or acceptance.completion_authorized is not False
    ):
        raise ValueError('Acceptance verification authority mismatch.')
    blockers.extend(acceptance.blockers)
    provenance = assess_installation_provenance(
        project=project, acceptance=acceptance
    )
    if (
        provenance.project_id != str(project.pk)
        or provenance.msr_id != str(msr.pk)
        or provenance.source_artifact_authenticated is not False
        or provenance.trusted_installation_evidence is not False
        or provenance.final_receipt_issuance_authorized is not False
        or provenance.completion_authorized is not False
    ):
        raise ValueError("Provenance authority mismatch.")
    blockers.extend(provenance.blockers)


    return InstallationCompletionEvidence(
        project_id=str(project.pk),
        operational_schedule_completed=valid,
        provisional_equipment_decisions_verified=provisional,
        completed_schedule_count=len(schedules),
        physical_unit_count=inspection.physical_unit_count,
        verified_inspection_candidate_count=inspection.verified_candidate_count,
        all_inspection_candidates_verified=inspection.all_candidates_verified,
        installation_provenance_status=provenance.status,
        installation_source_integrity_verified=(
            provenance.source_artifact_integrity_verified
        ),
        acceptance_candidate_verified=(
            acceptance.acceptance_candidate_verified
        ),
        post_installation_acceptance_verified=False,
        blockers=tuple(blockers),
    )
