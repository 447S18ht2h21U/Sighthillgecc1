from unittest.mock import patch
from django.test import SimpleTestCase
from core.api import ProjectSerializer
from core.models import Project

GUARD = "core.operational_project_api.operational_sales_status_available"

class ProjectSalesBrowser5032Tests(SimpleTestCase):

    def test_existing_fields_preserved(self):
        fields = ProjectSerializer().get_fields()
        for name in (
            "id", "code", "customer", "location",
            "sales_associate", "reviewer", "state",
            "current_approved", "pending", "created_at",
        ):
            self.assertIn(name, fields)

    def test_sales_status_is_read_only(self):
        field = ProjectSerializer().get_fields()["sales_status"]
        self.assertTrue(field.read_only)

    def test_disabled_guard_hides_sales_status(self):
        project = Project()
        project.sales_status = "LOST"
        with patch(GUARD, return_value=False):
            result = ProjectSerializer().get_sales_status(project)
        self.assertIsNone(result)

    def test_enabled_guard_preserves_project_state(self):
        project = Project()
        project.sales_status = "LOST"
        original_state = project.state
        with patch(GUARD, return_value=True):
            result = ProjectSerializer().get_sales_status(project)
        self.assertEqual(result, "LOST")
        self.assertEqual(project.state, original_state)
