"""Regression tests for the descriptive, default-deny access catalog."""

from django.test import SimpleTestCase

from .access_permission_catalog import (
    PERMISSIONS,
    PERMISSION_BY_CODE,
    describe_permission,
    has_permission,
)


class AccessPermissionCatalogTests(SimpleTestCase):

    def test_codes_are_unique_and_metadata_is_available(self):
        codes = [item.code for item in PERMISSIONS]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(len(codes), len(PERMISSION_BY_CODE))

        for item in PERMISSIONS:
            self.assertEqual(describe_permission(item.code), item)
            self.assertTrue(item.label)
            self.assertTrue(item.category)
            self.assertTrue(item.action)

        self.assertIsNone(describe_permission("unknown.permission"))

    def test_required_independent_access_categories_exist(self):
        required = {
            "dashboard.view",
            "customers.view",
            "customers.manage",
            "documents.sow.view",
            "documents.completion_financed.view",
            "documents.completion_non_financed.view",
            "documents.invoice.view",
            "documents.satisfaction_survey.view",
            "marketing_reports.view",
            "technician_assignments.view",
            "technician_assignments.create",
            "technician_assignments.end",
            "compensation.own.view",
            "compensation.all.view",
            "payroll_payments.approve",
            "financials.operations.view",
            "financials.cashflow.view",
            "financials.balance_sheet.view",
            "users.manage",
            "positions.manage",
        }

        self.assertTrue(required.issubset(PERMISSION_BY_CODE))

    def test_all_permissions_deny_without_integrated_authorization(self):
        for code in PERMISSION_BY_CODE:
            with self.subTest(permission=code):
                self.assertFalse(has_permission(None, code))
                self.assertFalse(
                    has_permission(
                        object(),
                        code,
                        project=object(),
                    )
                )

        self.assertFalse(has_permission(None, "unknown.permission"))

    def test_sensitive_rights_require_separate_approval_metadata(self):
        sensitive_approval = {
            "technician_assignments.create",
            "technician_assignments.end",
            "compensation.all.view",
            "payroll_payments.approve",
            "financials.operations.view",
            "financials.cashflow.view",
            "financials.balance_sheet.view",
            "users.manage",
            "positions.manage",
        }

        for code in sensitive_approval:
            with self.subTest(permission=code):
                item = PERMISSION_BY_CODE[code]
                self.assertTrue(item.sensitive)
                self.assertTrue(item.independent_approval)

        self.assertNotEqual(
            PERMISSION_BY_CODE["compensation.own.view"].code,
            PERMISSION_BY_CODE["compensation.all.view"].code,
        )

        self.assertNotEqual(
            PERMISSION_BY_CODE["users.manage"].code,
            PERMISSION_BY_CODE["positions.manage"].code,
        )

    def test_technician_changes_remain_project_scoped(self):
        for code in (
            "technician_assignments.view",
            "technician_assignments.create",
            "technician_assignments.end",
        ):
            with self.subTest(permission=code):
                self.assertTrue(PERMISSION_BY_CODE[code].project_scoped)

        self.assertFalse(
            has_permission(None, "technician_assignments.create")
        )
        self.assertFalse(
            has_permission(None, "technician_assignments.end")
        )
