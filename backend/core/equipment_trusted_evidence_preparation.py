"""Unregistered trusted-evidence PREPARATION only.

Combines the real recorder account, current approved MSR and physical
unit checks. Never issues trusted evidence or installation authority.
"""
from dataclasses import dataclass

from .equipment_physical_capture_actor_preview import (
    preview_identified_physical_capture,
)


@dataclass(frozen=True)
class TrustedEvidencePreparation:
    msr_id: str
    unit_id: str
    normalized_serial: str
    preparation_complete: bool
    blockers: tuple[str, ...]
    trusted_evidence_created: bool = False
    physical_verification_trusted: bool = False
    installation_authorized: bool = False


def prepare_physical_equipment_evidence(
    *, project_id, msr_id, unit_id, serial_number,
    recorder_id, captured_at, installation_starts_at,
):
    """Read existing records; evaluate candidate inputs; perform no writes."""
    result = preview_identified_physical_capture(
        project_id=project_id,
        msr_id=msr_id,
        unit_id=unit_id,
        serial_number=serial_number,
        recorder_id=recorder_id,
        captured_at=captured_at,
        installation_starts_at=installation_starts_at,
    )

    # A structural candidate never constitutes physical verification.
    # No caller-supplied trust flag is accepted by this interface.
    return TrustedEvidencePreparation(
        msr_id=result.msr_id,
        unit_id=result.unit_id,
        normalized_serial=result.normalized_serial,
        preparation_complete=result.candidate_valid is True,
        blockers=tuple(result.blockers),
    )