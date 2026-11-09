"""MSR delegation persistence models. No operational access is enabled.

Schema definitions only until separately authorized migrations, database
triggers, transactional services and access regression tests are complete.
"""

from django.db import models
from django.db.models import F, Q
from .models import Entity, Project, User


class MSRDelegationRequest(Entity):
    manager = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    recipient = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    source_associate = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.TextField()
    read_only = models.BooleanField(default=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")),
                name="msr_delegation_valid_window",
            ),
            models.CheckConstraint(
                condition=Q(read_only=True),
                name="msr_delegation_read_only",
            ),
        ]


class MSRDelegationRequestProject(Entity):
    request = models.ForeignKey(
        MSRDelegationRequest, on_delete=models.PROTECT,
        related_name="project_scopes",
    )
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    owner_revision = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["request", "project"],
                name="msr_delegation_unique_project",
            )
        ]


class MSRDelegationDecision(Entity):
    class Result(models.TextChoices):
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    request = models.OneToOneField(
        MSRDelegationRequest, on_delete=models.PROTECT,
        related_name="final_decision",
    )
    decided_by = models.ForeignKey(User, on_delete=models.PROTECT)
    result = models.CharField(max_length=12, choices=Result.choices)
    decided_at = models.DateTimeField()
    reason = models.TextField()
    authority_reference = models.TextField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(result__in=["APPROVED", "REJECTED"]),
                name="msr_delegation_valid_decision",
            ),
        ]


class MSRDelegationTermination(Entity):
    class Kind(models.TextChoices):
        SURRENDER = "VOLUNTARY_SURRENDER", "Voluntary surrender"
        REVOCATION = "ADMINISTRATIVE_REVOCATION", "Administrative revocation"
        EXPIRATION = "AUTOMATIC_EXPIRATION", "Automatic expiration"

    decision = models.OneToOneField(
        MSRDelegationDecision, on_delete=models.PROTECT,
        related_name="termination",
    )
    terminated_by = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True,
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    terminated_at = models.DateTimeField()
    reason = models.TextField()
    authority_reference = models.TextField(blank=True)


class MSRDelegationProjectInvalidation(Entity):
    decision = models.ForeignKey(
        MSRDelegationDecision, on_delete=models.PROTECT,
    )
    scope = models.OneToOneField(
        MSRDelegationRequestProject, on_delete=models.PROTECT,
        related_name="invalidation",
    )
    previous_revision = models.PositiveBigIntegerField()
    new_revision = models.PositiveBigIntegerField()
    invalidated_at = models.DateTimeField()
    reason = models.CharField(max_length=40, default="PROJECT_REASSIGNED")
    evidence_reference = models.TextField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(new_revision__gt=F("previous_revision")),
                name="msr_delegation_revision_increases",
            ),
            models.CheckConstraint(
                condition=Q(reason="PROJECT_REASSIGNED"),
                name="msr_delegation_invalidation_reason",
            ),
        ]