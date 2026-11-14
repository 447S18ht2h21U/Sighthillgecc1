from types import SimpleNamespace

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase

from .models import Project, ProjectSalesStatusChange
from .sales_status_service_5000 import (
    AUTHORIZED_ROLES,
    validate_sales_status_change,
)


def actor(role, active=True):
    return SimpleNamespace(
        role=role,
        is_active=active,
        is_authenticated=True,
    )


class SalesStatusService5000Tests(SimpleTestCase):
    def test_sales_manager_and_ceo_authorized(self):
        self.assertEqual(
            AUTHORIZED_ROLES, {"CEO", "SALES_MANAGER"}
        )
        for role in AUTHORIZED_ROLES:
            self.assertEqual(
                validate_sales_status_change(
                    actor(role), "LOST", "Customer declined proposal"
                ),
                "Customer declined proposal",
            )

    def test_other_roles_denied(self):
        for role in (
            "SALES_ASSOCIATE",
            "TECHNICIAN",
            "INSTALLATION_MANAGER",
            "COMPTROLLER",
            "MARKETING",
        ):
            with self.assertRaises(PermissionDenied):
                validate_sales_status_change(
                    actor(role), "LOST", "Customer declined proposal"
                )

    def test_inactive_actor_denied(self):
        with self.assertRaises(PermissionDenied):
            validate_sales_status_change(
                actor("CEO", active=False),
                "LOST",
                "Customer declined proposal",
            )

    def test_invalid_status_denied(self):
        with self.assertRaises(ValidationError):
            validate_sales_status_change(
                actor("CEO"), "COMPLETED", "Customer declined proposal"
            )

    def test_missing_reason_denied(self):
        with self.assertRaises(ValidationError):
            validate_sales_status_change(actor("CEO"), "LOST", "short")

    def test_audit_structure_retains_previous_and_new_status(self):
        self.assertIsNotNone(
            ProjectSalesStatusChange._meta.get_field("previous_status")
        )
        self.assertIsNotNone(
            ProjectSalesStatusChange._meta.get_field("new_status")
        )
        self.assertIsNotNone(
            ProjectSalesStatusChange._meta.get_field("reason")
        )
        self.assertIsNotNone(
            ProjectSalesStatusChange._meta.get_field("changed_by")
        )

    def test_project_state_remains_independent(self):
        self.assertIsNot(
            Project._meta.get_field("state"),
            Project._meta.get_field("sales_status"),
        )
