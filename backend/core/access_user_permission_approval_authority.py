"""Default-deny design for VERIDIAN permission approval authority.

This module assigns no new approval rights.
An explicit, separately reviewed authority matrix is required before
persistent permission decisions or operational access can be enabled.
"""

from dataclasses import dataclass

from .access_permission_catalog import PERMISSION_BY_CODE


@dataclass(frozen=True)
class PermissionAuthorityRequirement:
    permission_code: str
    sensitive: bool
    independent_approval: bool
    allowed_approver_roles: frozenset[str]
    allowed_administrative_revoker_roles: frozenset[str]
    live_authorization_enabled: bool = False


AUTHORITY_REQUIREMENTS = {
    code: PermissionAuthorityRequirement(
        permission_code=code,
        sensitive=definition.sensitive,
        independent_approval=definition.independent_approval,
        allowed_approver_roles=frozenset(),
        allowed_administrative_revoker_roles=frozenset(),
    )
    for code, definition in PERMISSION_BY_CODE.items()
}


def authority_matrix_is_complete():
    """No operational authority matrix has been approved or installed."""

    return False


def proposed_permission_request_requires_review(permission_code):
    """Unknown permissions are rejected; known requests grant nothing."""

    return permission_code in AUTHORITY_REQUIREMENTS


def proposed_permission_approval_allowed(
    *,
    permission_code,
    approver_role,
    approver_id,
    requester_id,
    recipient_id,
    approver_active,
    trusted_authority_verified=False,
):
    """Fail closed until an independently approved authority matrix exists."""

    requirement = AUTHORITY_REQUIREMENTS.get(permission_code)

    if requirement is None:
        return False

    if not requirement.live_authorization_enabled:
        return False

    if not authority_matrix_is_complete():
        return False

    if approver_active is not True:
        return False

    if trusted_authority_verified is not True:
        return False

    if approver_id is None or approver_id in {
        requester_id,
        recipient_id,
    }:
        return False

    return approver_role in requirement.allowed_approver_roles


def proposed_permission_administrative_revocation_allowed(
    *,
    permission_code,
    revoker_role,
    revoker_active,
    trusted_authority_verified=False,
):
    """Fail closed for administrative revocation authority."""

    requirement = AUTHORITY_REQUIREMENTS.get(permission_code)

    if requirement is None:
        return False

    if not requirement.live_authorization_enabled:
        return False

    if not authority_matrix_is_complete():
        return False

    if revoker_active is not True:
        return False

    if trusted_authority_verified is not True:
        return False

    return revoker_role in requirement.allowed_administrative_revoker_roles


def permission_authority_design_activates_access(*args, **kwargs):
    """Descriptive policy never enables operational access."""

    return False