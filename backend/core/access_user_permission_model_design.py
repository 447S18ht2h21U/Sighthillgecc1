"""Isolated Django model design for VERIDIAN permission evidence.

DESIGN ONLY:
- Do not import this module into models.py or app startup.
- Do not register these classes with Django.
- Do not generate or install migrations from this file.
- Do not use these descriptions to activate permissions.

The structures below are AST-inspectable design metadata, not model
classes and not database tables. This prevents accidental Django
registration before the migration safety review is complete.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelFieldDesign:
    name: str
    django_field: str
    required: bool = True


@dataclass(frozen=True)
class DjangoModelDesign:
    name: str
    fields: tuple[ModelFieldDesign, ...]
    immutable: bool = True
    registered: bool = False


REQUEST_MODEL = DjangoModelDesign(
    name="UserPermissionRequest",
    fields=(
        ModelFieldDesign("id", "UUIDField(primary_key=True)"),
        ModelFieldDesign("created_at", "DateTimeField(auto_now_add=True)"),
        ModelFieldDesign("recipient", "ForeignKey(User, PROTECT)"),
        ModelFieldDesign("requested_by", "ForeignKey(User, PROTECT)"),
        ModelFieldDesign("permission_code", "CharField(max_length=120)"),
        ModelFieldDesign("reason", "TextField()"),
        ModelFieldDesign("requested_at", "DateTimeField()"),
        ModelFieldDesign("starts_at", "DateTimeField()"),
        ModelFieldDesign("ends_at", "DateTimeField()"),
        ModelFieldDesign("digest", "CharField(max_length=64)"),
    ),
)

DECISION_MODEL = DjangoModelDesign(
    name="UserPermissionDecision",
    fields=(
        ModelFieldDesign("id", "UUIDField(primary_key=True)"),
        ModelFieldDesign("created_at", "DateTimeField(auto_now_add=True)"),
        ModelFieldDesign(
            "request",
            "OneToOneField(UserPermissionRequest, PROTECT)",
        ),
        ModelFieldDesign("decided_by", "ForeignKey(User, PROTECT)"),
        ModelFieldDesign("decision", "CharField(APPROVED|REJECTED)"),
        ModelFieldDesign("decided_at", "DateTimeField()"),
        ModelFieldDesign("reason", "TextField()"),
        ModelFieldDesign("authority_evidence", "TextField()"),
        ModelFieldDesign("digest", "CharField(max_length=64)"),
    ),
)

TERMINATION_MODEL = DjangoModelDesign(
    name="UserPermissionTermination",
    fields=(
        ModelFieldDesign("id", "UUIDField(primary_key=True)"),
        ModelFieldDesign("created_at", "DateTimeField(auto_now_add=True)"),
        ModelFieldDesign(
            "decision",
            "OneToOneField(UserPermissionDecision, PROTECT)",
        ),
        ModelFieldDesign(
            "terminated_by",
            "ForeignKey(User, PROTECT, null=True)",
            required=False,
        ),
        ModelFieldDesign(
            "termination_kind",
            "CharField(VOLUNTARY_SURRENDER|ADMINISTRATIVE_REVOCATION|AUTOMATIC_EXPIRATION)",
        ),
        ModelFieldDesign("terminated_at", "DateTimeField()"),
        ModelFieldDesign("reason", "TextField()"),
        ModelFieldDesign("authority_evidence", "TextField()"),
        ModelFieldDesign("digest", "CharField(max_length=64)"),
    ),
)


MODEL_DESIGNS = (
    REQUEST_MODEL,
    DECISION_MODEL,
    TERMINATION_MODEL,
)


REQUIRED_DATABASE_GUARDS = (
    "All evidence tables reject UPDATE.",
    "All evidence tables reject DELETE.",
    "All evidence relationships use protected foreign keys.",
    "Decisions reference exactly one existing request.",
    "Terminations reference exactly one approved decision.",
    "Decision and termination references are unique.",
    "Request effective dates have valid ordering.",
    "Decision actor is independent of requester and recipient.",
    "Decision authority is verified from trusted records.",
    "Administrative termination authority is verified from trusted records.",
    "Voluntary surrender identity is verified from trusted records.",
    "Automatic expiration does not require a termination write.",
    "Financial and Technician permissions retain their separate safeguards.",
    "Evidence creation and audit/outbox records are atomic.",
    "SQLite and PostgreSQL database protections are independently tested.",
)


def model_design_is_non_operational():
    return all(not item.registered for item in MODEL_DESIGNS)


def model_design_grants_access(*args, **kwargs):
    return False