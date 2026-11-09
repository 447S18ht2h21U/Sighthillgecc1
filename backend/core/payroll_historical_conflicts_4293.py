"""Non-operational consistency checks for historical payroll evidence.

This service checks proposed evidence objects only. It does not validate
database origin, approval, immutability, or authorization. No live
payroll retrieval is permitted through this module.
"""
from .payroll_historical_evidence_4292 import (
    candidate_historical_role,
)


def candidate_unambiguous_historical_role(
    evidence_records, *, subject_id, project_id, earned_on
):
    """Fail closed on missing, invalid, duplicate, or conflicting records.

    A future trusted resolver must independently prove that the supplied
    collection is complete and comes from approved immutable history.
    """
    if type(evidence_records) not in (list, tuple):
        return None
    if len(evidence_records) != 1:
        return None

    return candidate_historical_role(
        evidence_records[0],
        subject_id=subject_id,
        project_id=project_id,
        earned_on=earned_on,
    )


def historical_conflict_resolution_grants_access(*args, **kwargs):
    """Consistency checks never establish effective permission."""
    return False