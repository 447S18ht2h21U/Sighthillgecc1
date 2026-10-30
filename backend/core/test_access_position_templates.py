"""Regression tests for VERIDIAN position-template planning metadata."""

from django.test import SimpleTestCase

from .models import Role
from .access_position_templates import (
    POSITION_TEMPLATES,
    POSITION_BY_CODE,
    describe_position,
    position_grants_permission,
)
from .access_permission_catalog import PERMISSION_BY_CODE


class AccessPositionTemplateTests(SimpleTestCase):

    def test_templates_match_existing_business_roles(self):
        expected = {value for value, label in Role.choices}
        actual = {template.code for template in POSITION_TEMPLATES}
        self.assertEqual(actual, expected)
        self.assertEqual(len(POSITION_TEMPLATES), 9)

    def test_position_codes_are_unique(self):
        codes = [template.code for template in POSITION_TEMPLATES]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(len(codes), len(POSITION_BY_CODE))

    def test_all_position_templates_start_without_permissions(self):
        for template in POSITION_TEMPLATES:
            with self.subTest(position=template.code):
                self.assertEqual(template.proposed_permissions, ())
                self.assertTrue(template.label)
                self.assertEqual(describe_position(template.code), template)

    def test_position_templates_never_grant_access(self):
        for template in POSITION_TEMPLATES:
            for permission_code in PERMISSION_BY_CODE:
                with self.subTest(
                    position=template.code,
                    permission=permission_code,
                ):
                    self.assertFalse(
                        position_grants_permission(
                            template.code,
                            permission_code,
                        )
                    )

    def test_unknown_positions_and_permissions_deny(self):
        self.assertIsNone(describe_position("UNKNOWN"))
        self.assertFalse(
            position_grants_permission("UNKNOWN", "dashboard.view")
        )
        self.assertFalse(
            position_grants_permission("COMPTROLLER", "unknown.permission")
        )
