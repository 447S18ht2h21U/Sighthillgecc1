"""Trusted, read-only project ownership checks for proposed MSR delegation.

This service validates persisted project ownership only. It does not
approve requests, activate permissions, or modify the MSR visibility API.
"""

from django.db import transaction

from .models import Project, Role, User


def verify_msr_delegation_project_ownership(
    *,
    manager_id,
    recipient_id,
    source_associate_id,
    project_ids,
):
    """Return a fixed project snapshot or deny the entire request."""

    if not isinstance(project_ids, (tuple, list)):
        return None

    if not 1 <= len(project_ids) <= 100:
        return None

    try:
        selected = tuple(str(value) for value in project_ids)
        if len(set(selected)) != len(selected):
            return None

        with transaction.atomic():
            manager = User.objects.filter(
                pk=manager_id,
                role=Role.SALES_MANAGER,
                is_active=True,
            ).first()

            recipient = User.objects.filter(
                pk=recipient_id,
                role=Role.SALES_ASSOCIATE,
                is_active=True,
            ).first()

            source = User.objects.filter(
                pk=source_associate_id,
                role=Role.SALES_ASSOCIATE,
            ).first()

            if manager is None or recipient is None or source is None:
                return None

            if len({manager.pk, recipient.pk, source.pk}) != 3:
                return None

            projects = list(
                Project.objects.filter(
                    pk__in=selected,
                    sales_associate_id=source.pk,
                ).values_list("pk", flat=True)
            )

            if len(projects) != len(selected):
                return None

            found = set(str(value) for value in projects)

            if found != set(selected):
                return None

            return tuple(projects)

    except (TypeError, ValueError, OverflowError):
        return None


def verified_ownership_grants_msr_access(*args, **kwargs):
    """Ownership evidence alone never grants delegated MSR access."""
    return False