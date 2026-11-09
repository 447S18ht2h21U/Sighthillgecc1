"""Fail-closed ownership-revision checks for proposed MSR delegation.

Security foundation only. Does not approve, grant or activate MSR access.
Snapshots MUST be constructed from verified database records, not client
claims. A later persistence service must enforce atomic revision changes.
"""

from dataclasses import dataclass
from uuid import UUID


MAX_REVISION = (1 << 63) - 1


def _identifier(value):
    if isinstance(value, UUID):
        return value
    if type(value) is not str:
        return None
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        return None
    return parsed if str(parsed) == value else None


def _revision(value):
    return (
        type(value) is int
        and 0 <= value <= MAX_REVISION
    )


@dataclass(frozen=True)
class VerifiedOwnershipSnapshot:
    project_id: UUID
    owner_id: UUID
    revision: int


def make_ownership_snapshot(*, project_id, owner_id, revision):
    project = _identifier(project_id)
    owner = _identifier(owner_id)
    if project is None or owner is None or not _revision(revision):
        return None
    return VerifiedOwnershipSnapshot(project, owner, revision)


def ownership_matches(snapshot, *, project_id, owner_id, revision):
    if type(snapshot) is not VerifiedOwnershipSnapshot:
        return False
    project = _identifier(project_id)
    owner = _identifier(owner_id)
    if project is None or owner is None or not _revision(revision):
        return False
    return (
        snapshot.project_id == project
        and snapshot.owner_id == owner
        and snapshot.revision == revision
    )


def valid_reassignment(before, after):
    if (
        type(before) is not VerifiedOwnershipSnapshot
        or type(after) is not VerifiedOwnershipSnapshot
    ):
        return False
    return (
        before.project_id == after.project_id
        and before.owner_id != after.owner_id
        and before.revision < MAX_REVISION
        and after.revision == before.revision + 1
    )


def ownership_revision_grants_msr_access(*args, **kwargs):
    """This evidence helper never authorizes operational access."""
    return False