"""Security tests for the non-operational permission authority framework."""

from uuid import uuid4

from django.test import SimpleTestCase

from .access_permission_catalog import PERMISSION_BY_CODE
from .access_user_permission_approval_authority import (
    AUTHORITY_REQUIREMENTS,
    authority_matrix_is_complete,
    permission_authority_design_activates_access,
    proposed_permission_administrative_revocation_allowed,
    proposed_permission_approval_allowed,
    proposed_permission_request_requires_review,
)


class UserPermissionApprovalAuthorityTests(SimpleTestCase):

    def setUp(self):
        self.recipient = uuid4()
        self.requester = uuid4()
        self.approver = uuid4()

    def approval(self, **changes):
        values = {
            "permission_code": "compensation.all.view",
            "approver_role": "CEO",
            "approver_id": self.approver,
            "requester_id": self.requester,
            "recipient_id": self.recipient,
            "approver_active": True,
            "trusted_authority_verified": True,
        }
        values.update(changes)
        return proposed_permission_approval_allowed(**values)

    def revocation(self, **changes):
        values = {
            "permission_code": "compensation.all.view",
            "revoker_role": "COMPTROLLER",
            "revoker_active": True,
            "trusted_authority_verified": True,
        }
        values.update(changes)
        return proposed_permission_administrative_revocation_allowed(**values)

    def test_every_catalog_permission_is_covered(self):
        self.assertEqual(
            set(AUTHORITY_REQUIREMENTS),
            set(PERMISSION_BY_CODE),
        )

    def test_all_permission_codes_match_their_requirements(self):
        for code, requirement in AUTHORITY_REQUIREMENTS.items():
            with self.subTest(permission=code):
                self.assertEqual(requirement.permission_code, code)

    def test_catalog_sensitivity_is_preserved(self):
        for code, definition in PERMISSION_BY_CODE.items():
            with self.subTest(permission=code):
                self.assertEqual(
                    AUTHORITY_REQUIREMENTS[code].sensitive,
                    definition.sensitive,
                )

    def test_independent_approval_flags_are_preserved(self):
        for code, definition in PERMISSION_BY_CODE.items():
            with self.subTest(permission=code):
                self.assertEqual(
                    AUTHORITY_REQUIREMENTS[code].independent_approval,
                    definition.independent_approval,
                )

    def test_no_approver_roles_are_assigned(self):
        self.assertTrue(all(
            not requirement.allowed_approver_roles
            for requirement in AUTHORITY_REQUIREMENTS.values()
        ))

    def test_no_administrative_revoker_roles_are_assigned(self):
        self.assertTrue(all(
            not requirement.allowed_administrative_revoker_roles
            for requirement in AUTHORITY_REQUIREMENTS.values()
        ))

    def test_live_authorization_disabled_for_every_permission(self):
        self.assertTrue(all(
            requirement.live_authorization_enabled is False
            for requirement in AUTHORITY_REQUIREMENTS.values()
        ))

    def test_authority_matrix_is_incomplete(self):
        self.assertFalse(authority_matrix_is_complete())

    def test_known_requests_require_review(self):
        for code in PERMISSION_BY_CODE:
            with self.subTest(permission=code):
                self.assertTrue(
                    proposed_permission_request_requires_review(code)
                )

    def test_unknown_permission_request_denied(self):
        self.assertFalse(
            proposed_permission_request_requires_review(
                "unknown.permission"
            )
        )

    def test_ceo_cannot_approve_without_authority_matrix(self):
        self.assertFalse(self.approval(approver_role="CEO"))

    def test_comptroller_cannot_approve_without_authority_matrix(self):
        self.assertFalse(self.approval(approver_role="COMPTROLLER"))

    def test_claimed_trusted_authority_cannot_bypass_default_deny(self):
        self.assertFalse(
            self.approval(trusted_authority_verified=True)
        )

    def test_self_approval_is_denied(self):
        self.assertFalse(self.approval(
            approver_id=self.recipient
        ))

    def test_requester_approval_is_denied(self):
        self.assertFalse(self.approval(
            approver_id=self.requester
        ))

    def test_inactive_approver_is_denied(self):
        self.assertFalse(self.approval(
            approver_active=False
        ))

    def test_unknown_permission_approval_is_denied(self):
        self.assertFalse(self.approval(
            permission_code="unknown.permission"
        ))

    def test_all_catalog_permissions_deny_live_approval(self):
        for code in PERMISSION_BY_CODE:
            with self.subTest(permission=code):
                self.assertFalse(
                    self.approval(permission_code=code)
                )

    def test_ceo_cannot_revoke_without_authority_matrix(self):
        self.assertFalse(self.revocation(
            revoker_role="CEO"
        ))

    def test_comptroller_cannot_revoke_without_authority_matrix(self):
        self.assertFalse(self.revocation(
            revoker_role="COMPTROLLER"
        ))

    def test_inactive_revoker_is_denied(self):
        self.assertFalse(self.revocation(
            revoker_active=False
        ))

    def test_unknown_permission_revocation_is_denied(self):
        self.assertFalse(self.revocation(
            permission_code="unknown.permission"
        ))

    def test_all_catalog_permissions_deny_live_revocation(self):
        for code in PERMISSION_BY_CODE:
            with self.subTest(permission=code):
                self.assertFalse(
                    self.revocation(permission_code=code)
                )

    def test_descriptive_authority_never_activates_access(self):
        self.assertFalse(
            permission_authority_design_activates_access(
                permission_code="compensation.all.view",
                recipient_id=self.recipient,
            )
        )