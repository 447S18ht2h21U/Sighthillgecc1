"""Focused acceptance for operational sales status visibility."""

import os
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.models import Project
from core.operational_project_api import (
    OperationalProjectSerializer,
    operational_sales_status_available,
)


class OperationalSalesStatus5029Tests(SimpleTestCase):

    def test_serializer_keeps_project_and_sales_fields_separate(self):
        serializer = OperationalProjectSerializer()
        fields = serializer.get_fields()

        self.assertIn("state", fields)
        self.assertIn("sales_status", fields)
        self.assertTrue(fields["sales_status"].read_only)

    def test_unavailable_sales_status_is_not_disclosed(self):
        project = Project()
        project.sales_status = "LOST"

        with patch(
            "core.operational_project_api."
            "operational_sales_status_available",
            return_value=False,
        ):
            serializer = OperationalProjectSerializer()
            self.assertIsNone(serializer.get_sales_status(project))

    def test_available_sales_status_is_returned_without_mutation(self):
        project = Project()
        project.sales_status = "LOST"
        original_state = project.state

        with patch(
            "core.operational_project_api."
            "operational_sales_status_available",
            return_value=True,
        ):
            serializer = OperationalProjectSerializer()
            self.assertEqual(
                serializer.get_sales_status(project), "LOST"
            )

        self.assertEqual(project.state, original_state)

    @override_settings(DEBUG=False)
    def test_production_mode_fails_closed(self):
        with patch.dict(
            os.environ, {"GECC_SALES_STATUS_ENABLED": "1"}
        ):
            self.assertFalse(operational_sales_status_available())

    @override_settings(DEBUG=True)
    def test_disabled_feature_fails_closed(self):
        with patch.dict(
            os.environ, {"GECC_SALES_STATUS_ENABLED": "0"}
        ):
            self.assertFalse(operational_sales_status_available())
