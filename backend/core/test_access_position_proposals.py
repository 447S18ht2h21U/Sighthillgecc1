"""Tests for the nonbinding VERIDIAN position-access proposals."""

from django.test import SimpleTestCase

from .access_permission_catalog import PERMISSION_BY_CODE, has_permission
from .access_position_templates import (
    POSITION_BY_CODE,
    position_grants_permission,
)
from .access_position_proposals import (
    PROPOSED_ACCESS,
    RESERVED_FOR_SEPARATE_APPROVAL,
    proposed_access_granted,
    proposed_permissions,
)


class AccessPositionProposalTests(SimpleTestCase):

    def test_every_position_has_a_proposal(self):
        self.assertEqual(set(PROPOSED_ACCESS), set(POSITION_BY_CODE))
        self.assertEqual(len(PROPOSED_ACCESS), 9)

    def test_proposals_use_known_unique_permissions(self):
        for position, codes in PROPOSED_ACCESS.items():
            with self.subTest(position=position):
                self.assertIsInstance(codes, tuple)
                self.assertEqual(len(codes), len(set(codes)))
                self.assertEqual(proposed_permissions(position), codes)
                self.assertTrue(set(codes).issubset(PERMISSION_BY_CODE))

    def test_independent_approval_rights_are_never_preassigned(self):
        expected_reserved = {
            code for code, definition in PERMISSION_BY_CODE.items()
            if definition.independent_approval
        }
        self.assertEqual(
            RESERVED_FOR_SEPARATE_APPROVAL,
            expected_reserved,
        )

        for position, codes in PROPOSED_ACCESS.items():
            with self.subTest(position=position):
                self.assertFalse(
                    set(codes) & RESERVED_FOR_SEPARATE_APPROVAL
                )

    def test_technician_management_is_not_granted_by_position(self):
        restricted = {
            "technician_assignments.create",
            "technician_assignments.end",
        }
        for position, codes in PROPOSED_ACCESS.items():
            with self.subTest(position=position):
                self.assertFalse(restricted & set(codes))

        self.assertFalse(
            position_grants_permission(
                "CEO", "technician_assignments.create"
            )
        )
        self.assertFalse(
            position_grants_permission(
                "CEO", "technician_assignments.end"
            )
        )

    def test_financial_and_administrative_approvals_are_reserved(self):
        restricted = {
            "compensation.all.view",
            "payroll_payments.approve",
            "financials.operations.view",
            "financials.cashflow.view",
            "financials.balance_sheet.view",
            "users.manage",
            "positions.manage",
        }
        for position, codes in PROPOSED_ACCESS.items():
            with self.subTest(position=position):
                self.assertFalse(restricted & set(codes))

    def test_proposals_cannot_grant_live_access(self):
        for position in POSITION_BY_CODE:
            for code in PERMISSION_BY_CODE:
                with self.subTest(position=position, permission=code):
                    self.assertFalse(
                        position_grants_permission(position, code)
                    )
                    self.assertFalse(
                        proposed_access_granted(
                            object(), code, project=object()
                        )
                    )
                    self.assertFalse(has_permission(None, code))

    def test_unknown_positions_and_permissions_fail_closed(self):
        self.assertEqual(proposed_permissions("UNKNOWN"), ())
        self.assertFalse(
            proposed_access_granted(None, "unknown.permission")
        )
        self.assertFalse(
            position_grants_permission("UNKNOWN", "dashboard.view")
        )
