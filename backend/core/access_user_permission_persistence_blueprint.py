"""Non-executable persistence blueprint for VERIDIAN user permissions.

This module defines proposed database structure and safeguards.
It creates no Django models, database tables, migrations, or access grants.

Historical approval and termination evidence remain separate.
Current access eligibility must be evaluated independently.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProposedRecord:
    name: str
    fields: tuple[str, ...]
    immutable: bool
    unique_parent: bool


PERMISSION_REQUEST = ProposedRecord(
    name="UserPermissionRequest",
    fields=(
        "id: UUID primary key",
        "created_at: timestamp",
        "recipient: protected User foreign key",
        "requested_by: protected User foreign key",
        "permission_code: catalog-validated string",
        "reason: required text",
        "requested_at: timezone-aware timestamp",
        "starts_at: timezone-aware timestamp",
        "ends_at: timezone-aware timestamp",
        "digest: SHA256 evidence digest",
    ),
    immutable=True,
    unique_parent=False,
)

PERMISSION_DECISION = ProposedRecord(
    name="UserPermissionDecision",
    fields=(
        "id: UUID primary key",
        "request: protected unique request foreign key",
        "decided_by: protected User foreign key",
        "decision: APPROVED or REJECTED",
        "decided_at: timezone-aware timestamp",
        "reason: required text",
        "authority_evidence: approval-time authorization reference",
        "digest: SHA256 evidence digest",
    ),
    immutable=True,
    unique_parent=True,
)

PERMISSION_TERMINATION = ProposedRecord(
    name="UserPermissionTermination",
    fields=(
        "id: UUID primary key",
        "decision: protected unique approved-decision foreign key",
        "terminated_by: nullable protected User foreign key",
        "termination_kind: surrender, revocation, or expiration",
        "terminated_at: timezone-aware timestamp",
        "reason: required text",
        "authority_evidence: termination-time authorization reference",
        "digest: SHA256 evidence digest",
    ),
    immutable=True,
    unique_parent=True,
)


RECORDS = (
    PERMISSION_REQUEST,
    PERMISSION_DECISION,
    PERMISSION_TERMINATION,
)


DATABASE_SAFEGUARDS = (
    "Reject updates to historical permission evidence.",
    "Reject deletion of permission evidence.",
    "Require requests to precede decisions.",
    "Require independent approval or rejection.",
    "Require approval before termination.",
    "Prevent duplicate decisions for the same request.",
    "Prevent duplicate terminations for the same approval.",
    "Reject invalid or reversed effective periods.",
    "Require a documented reason for each decision and termination.",
    "Require trusted authority verification at decision time.",
    "Require trusted authority verification for administrative revocation.",
    "Require recipient identity verification for voluntary surrender.",
    "Require atomic evidence, audit, and outbox writes.",
    "Never activate access from evidence creation alone.",
    "Deny access after expiry even without an expiration record.",
    "Deny access immediately after surrender or revocation.",
    "Never reactivate terminated evidence; require a new request.",
    "Preserve historical approvals when the approver later becomes inactive.",
    "Implement equivalent SQLite and PostgreSQL safeguards.",
    "Do not install protected migration 0071 on the development database.",
)


def blueprint_is_structurally_complete():
    """Validate blueprint metadata only, never database readiness."""

    expected = {
        "UserPermissionRequest",
        "UserPermissionDecision",
        "UserPermissionTermination",
    }

    return (
        {record.name for record in RECORDS} == expected
        and all(record.immutable for record in RECORDS)
        and not PERMISSION_REQUEST.unique_parent
        and PERMISSION_DECISION.unique_parent
        and PERMISSION_TERMINATION.unique_parent
        and len(DATABASE_SAFEGUARDS) == 20
    )


def blueprint_enables_permissions(*args, **kwargs):
    """Design metadata cannot activate operational access."""

    return False


def blueprint_installs_migrations(*args, **kwargs):
    """Migration installation is explicitly outside this design."""

    return False