"""Non-executable database safeguard specification for user permissions.

No SQL is executed, no Django models are registered, and no migrations
are generated or installed by this module.

The specification distinguishes database integrity from trusted
business authorization. Neither layer may be substituted for the other.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TableSafeguards:
    model: str
    immutable_after_insert: bool
    reject_delete: bool
    required_insert_checks: tuple[str, ...]
    required_constraints: tuple[str, ...]


REQUEST_SAFEGUARDS = TableSafeguards(
    model="UserPermissionRequest",
    immutable_after_insert=True,
    reject_delete=True,
    required_insert_checks=(
        "Recipient and requester must reference existing users.",
        "Permission code must be in the approved catalog.",
        "Reason must contain non-whitespace text.",
        "Requested and effective timestamps must be valid.",
        "Effective start must precede effective end.",
        "Request must not contain decision or termination evidence.",
    ),
    required_constraints=(
        "UUID primary key.",
        "Protected recipient foreign key.",
        "Protected requester foreign key.",
        "Required evidence digest.",
        "Valid effective period.",
    ),
)

DECISION_SAFEGUARDS = TableSafeguards(
    model="UserPermissionDecision",
    immutable_after_insert=True,
    reject_delete=True,
    required_insert_checks=(
        "Decision must reference an existing request.",
        "Decision must be APPROVED or REJECTED.",
        "Decision-maker cannot equal requester.",
        "Decision-maker cannot equal recipient.",
        "Decision timestamp cannot precede request timestamp.",
        "Reason and authority evidence must be present.",
    ),
    required_constraints=(
        "UUID primary key.",
        "Unique protected request relationship.",
        "Protected decision-maker foreign key.",
        "Required evidence digest.",
    ),
)

TERMINATION_SAFEGUARDS = TableSafeguards(
    model="UserPermissionTermination",
    immutable_after_insert=True,
    reject_delete=True,
    required_insert_checks=(
        "Termination must reference an existing approved decision.",
        "Termination must have a permitted termination kind.",
        "Termination timestamp cannot precede approval.",
        "Voluntary surrender must identify the recipient.",
        "Administrative revocation must identify an authorized actor.",
        "Automatic expiration cannot precede the effective end.",
        "Termination reason and authority evidence must be present.",
    ),
    required_constraints=(
        "UUID primary key.",
        "Unique protected decision relationship.",
        "Protected nullable terminating-user foreign key.",
        "Required evidence digest.",
    ),
)


TABLE_SAFEGUARDS = (
    REQUEST_SAFEGUARDS,
    DECISION_SAFEGUARDS,
    TERMINATION_SAFEGUARDS,
)


TRUSTED_SERVICE_REQUIREMENTS = (
    "Authenticate actors using persisted user records.",
    "Verify officer authority at the moment of decision.",
    "Verify termination authority at the moment of revocation.",
    "Verify recipient identity at the moment of surrender.",
    "Use database transactions and appropriate row locks.",
    "Write evidence, audit events, and outbox entries atomically.",
    "Reject caller-supplied claims as proof of authorization.",
    "Maintain existing Technician assignment authorization restrictions.",
    "Maintain existing payroll and compensation authorization restrictions.",
    "Preserve historical decisions after subsequent officer role changes.",
    "Evaluate current eligibility separately from historical evidence.",
    "Fail closed until explicit operational integration is approved.",
)


DATABASE_IMPLEMENTATION_REQUIREMENTS = (
    "Implement equivalent SQLite and PostgreSQL protections.",
    "Enforce database-level update and delete prevention.",
    "Enforce uniqueness through database constraints.",
    "Enforce cross-record rules through tested triggers or equivalent controls.",
    "Test malformed direct SQL inserts against isolated databases.",
    "Test concurrent decisions and terminations.",
    "Preserve migration 0071 installation restrictions.",
    "Do not deploy permission schema before migration-chain review.",
)


def database_safeguards_are_operational():
    """Specification metadata does not establish database enforcement."""

    return False


def database_safeguards_grant_access(*args, **kwargs):
    """No access can be granted by a database design document."""

    return False

POSTGRESQL_PRIVILEGED_PROCEDURE_REQUIREMENTS = (
    "Use a dedicated non-login owner for protected tables and privileged procedures.",
    "Use a restricted application role without direct INSERT, UPDATE, DELETE, "
    "ALTER, or ownership rights over protected permission evidence.",
    "Revoke default PUBLIC execution privileges from privileged functions.",
    "Grant only specifically approved function execution to the application role.",
    "Use SECURITY DEFINER only for independently reviewed, narrowly scoped operations.",
    "Pin each privileged function search_path to trusted schemas and pg_catalog; "
    "keep writable schemas outside unqualified object resolution.",
    "Use explicit schema-qualified references for protected database objects.",
    "Never accept caller-supplied role names, authority flags, or authorization "
    "claims as proof of approval authority.",
    "Obtain verified actor identity through a trusted authentication boundary.",
    "Verify independent, current, permission-specific officer authority.",
    "Acquire a shared authority-row locking protocol before approval or revocation.",
    "Prevent concurrent approval and revocation from bypassing authority checks.",
    "Use database-controlled timestamps and preserve historical evidence.",
    "Write evidence, audit records, and required outbox events atomically.",
    "Reject unauthorized direct writes and attempts to alter historical evidence.",
    "Verify function ownership, function grants, schema privileges, and search_path.",
    "Test both approval-first and revocation-first transaction ordering.",
    "Fail closed if trusted authorization, integrity, or audit requirements fail.",
    "Do not activate permission grants before authority policy approval.",
    "Do not install migration 0071 on the development database.",
)


def postgresql_privileged_procedures_are_operational(*args, **kwargs):
    """Specification only; no privileged database procedure is installed."""
    return False
