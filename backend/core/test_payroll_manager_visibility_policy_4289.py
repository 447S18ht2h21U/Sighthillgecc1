"""Tests for proposed payroll classifications, never access grants."""

from django.test import SimpleTestCase

from .models import Role
from .payroll_manager_visibility_policy_4289 import (
    candidate_manager_payroll_visibility,
    manager_payroll_live_access,
)


class ManagerPayrollVisibilityPolicy4289Tests(SimpleTestCase):
    def candidate(self, viewer, subject, verified=True):
        return candidate_manager_payroll_visibility(
            viewer_role=viewer,
            subject_role=subject,
            historical_binding_verified=verified,
        )

    def test_sales_manager_category_is_sales_only(self):
        self.assertTrue(self.candidate(
            Role.SALES_MANAGER, Role.SALES_ASSOCIATE
        ))
        self.assertFalse(self.candidate(
            Role.SALES_MANAGER, Role.TECHNICIAN
        ))

    def test_installation_manager_category_is_technician_only(self):
        self.assertTrue(self.candidate(
            Role.INSTALLATION_MANAGER, Role.TECHNICIAN
        ))
        self.assertFalse(self.candidate(
            Role.INSTALLATION_MANAGER, Role.SALES_ASSOCIATE
        ))

    def test_executive_view_categories_do_not_grant_payment_authority(self):
        for viewer in (Role.CEO, Role.COMPTROLLER):
            for subject in (Role.SALES_ASSOCIATE, Role.TECHNICIAN):
                with self.subTest(viewer=viewer, subject=subject):
                    self.assertTrue(self.candidate(viewer, subject))
                    self.assertFalse(manager_payroll_live_access(
                        viewer_role=viewer, subject_role=subject
                    ))

    def test_missing_historical_binding_denies_every_role(self):
        for viewer in (
            Role.CEO, Role.COMPTROLLER, Role.SALES_MANAGER,
            Role.INSTALLATION_MANAGER
        ):
            self.assertFalse(self.candidate(
                viewer, Role.TECHNICIAN, verified=False
            ))
            self.assertFalse(self.candidate(
                viewer, Role.TECHNICIAN, verified=None
            ))

    def test_free_text_job_descriptions_are_not_role_evidence(self):
        # A string equal to a role code is not independent evidence.
        # This test deliberately supplies NO verified historical binding.
        for description in (
            "Sales Associate", "Technician", "Installer",
            "Sales and Installation", "", "TECHNICIAN"
        ):
            with self.subTest(description=description):
                self.assertFalse(self.candidate(
                    Role.SALES_MANAGER, description, verified=False
                ))
                self.assertFalse(self.candidate(
                    Role.INSTALLATION_MANAGER, description, verified=False
                ))
                self.assertFalse(manager_payroll_live_access(
                    viewer_role=Role.INSTALLATION_MANAGER,
                    subject_role=description,
                    historical_binding_verified=True,
                ))

    def test_other_roles_have_no_manager_scope(self):
        for viewer in (
            Role.SALES_ASSOCIATE,
            Role.TECHNICIAN,
            Role.MARKETING,
            Role.ACCOUNTS_PAYABLE_ASSOCIATE,
            Role.DATABASE_ADMINISTRATOR,
        ):
            with self.subTest(viewer=viewer):
                self.assertFalse(self.candidate(
                    viewer, Role.SALES_ASSOCIATE
                ))
                self.assertFalse(self.candidate(
                    viewer, Role.TECHNICIAN
                ))

    def test_invalid_roles_and_flags_fail_closed(self):
        for viewer in (None, "", "INVALID", True, 123):
            self.assertFalse(self.candidate(
                viewer, Role.TECHNICIAN
            ))
        for subject in (None, "", "INVALID", True, 123):
            self.assertFalse(self.candidate(
                Role.CEO, subject
            ))
        for flag in ("True", 1, [], {}):
            self.assertFalse(self.candidate(
                Role.CEO, Role.TECHNICIAN, verified=flag
            ))

    def test_candidate_never_enables_live_payroll_access(self):
        self.assertFalse(manager_payroll_live_access())
        self.assertFalse(manager_payroll_live_access(
            viewer_role=Role.COMPTROLLER,
            subject_role=Role.TECHNICIAN,
            historical_binding_verified=True,
        ))
        self.assertFalse(manager_payroll_live_access(
            viewer_role=Role.SALES_MANAGER,
            subject_role=Role.SALES_ASSOCIATE,
            historical_binding_verified=True,
        ))