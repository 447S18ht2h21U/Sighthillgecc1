"""Unregistered, read-only recorder identity verification.

The caller cannot supply a trusted role or active-status assertion.
No evidence creation or installation authorization.
"""
from uuid import UUID

from .equipment_physical_capture_candidate import PhysicalCaptureCandidate
from .equipment_physical_capture_db_preview import (
    preview_current_msr_physical_capture,
)
from .models import Role, User


def preview_identified_physical_capture(
    *, project_id, msr_id, unit_id, serial_number,
    recorder_id, captured_at, installation_starts_at,
):
    try:
        normalized_recorder = str(UUID(str(recorder_id)))
        normalized_msr = str(UUID(str(msr_id)))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("Valid recorder and MSR identifiers are required.") from None

    def blocked(message):
        return PhysicalCaptureCandidate(
            msr_id=normalized_msr,
            unit_id=unit_id if type(unit_id) is str else "",
            normalized_serial="",
            candidate_valid=False,
            blockers=(message,),
        )

    recorder = User.objects.filter(pk=normalized_recorder).first()
    if recorder is None:
        return blocked("Recorder account does not exist.")

    if recorder.is_active is not True or recorder.role != Role.INSTALLATION_MANAGER:
        return blocked("An active Installation Manager recorder is required.")

    # This is a read-only identity check, not proof of who physically
    # inspected the equipment or authority to capture trusted evidence.
    return preview_current_msr_physical_capture(
        project_id=project_id,
        msr_id=normalized_msr,
        unit_id=unit_id,
        serial_number=serial_number,
        recorder_id=normalized_recorder,
        recorder_role=recorder.role,
        recorder_active=recorder.is_active,
        captured_at=captured_at,
        installation_starts_at=installation_starts_at,
    )