"""Trusted identity checks for proposed MSR delegation approvals.

Read-only design service. It does not create, approve, persist, or
activate delegations, and is not connected to the registered MSR API.
"""

from .models import Role, User


AUTHORIZED_DECISION_ROLES = frozenset({
    Role.CEO,
    Role.COMPTROLLER,
})


def verify_msr_delegation_approval_authority(
    *,
    manager_id,
    recipient_id,
    source_associate_id,
    approver_id,
):
    """Return trusted identities only when the separation rules hold."""

    identities = (
        manager_id,
        recipient_id,
        source_associate_id,
        approver_id,
    )

    if any(value is None for value in identities):
        return None

    try:
        records = {
            str(user.pk): user
            for user in User.objects.filter(pk__in=identities)
        }
    except (TypeError, ValueError, OverflowError):
        return None

    if len(records) != 4:
        return None

    manager = records.get(str(manager_id))
    recipient = records.get(str(recipient_id))
    source = records.get(str(source_associate_id))
    approver = records.get(str(approver_id))

    if any(value is None for value in (
        manager, recipient, source, approver
    )):
        return None

    if not manager.is_active or manager.role != Role.SALES_MANAGER:
        return None

    if not recipient.is_active or recipient.role != Role.SALES_ASSOCIATE:
        return None

    if source.role != Role.SALES_ASSOCIATE:
        return None

    if not approver.is_active:
        return None

    if approver.role not in AUTHORIZED_DECISION_ROLES:
        return None

    return (
        manager.pk,
        recipient.pk,
        source.pk,
        approver.pk,
    )


def trusted_authority_check_grants_access(*args, **kwargs):
    """Verification alone cannot activate MSR viewing permissions."""
    return False