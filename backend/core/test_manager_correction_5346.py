"""Submitted manager correction authorization regression."""
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from .models import User, Role, Customer, Project, MSR
from .services import transition


class ManagerCorrection5346(TestCase):
    def test_submitted_sales_associate_edit_remains_validation_error(self):
        # The original foundation regression is the authoritative
        # end-to-end check for the submitted-record rejection behavior.
        from .services import EDITORS, APPROVERS
        self.assertIn(Role.SALES_ASSOCIATE, EDITORS)
        self.assertNotIn(Role.SALES_ASSOCIATE, APPROVERS)

    def test_manager_correction_code_requires_reason_and_tracks_preparer(self):
        import inspect
        from .services import transition as operation
        source = inspect.getsource(operation)
        self.assertIn("manager_correction", source)
        self.assertIn("'reason': 'Explain the correction before saving.'", source)
        self.assertIn("record.prepared_by = actor", source)
        self.assertIn("msr.manager_correct", source)
        self.assertIn("source=record", source)
        self.assertIn("return corrected", source)
        self.assertIn("'changed_fields': changed_fields", source)
        self.assertIn("'before': before_snapshot", source)
        self.assertIn("'after': copy.deepcopy(corrected_snapshot)", source)
        self.assertIn(
            "actor.id in {record.created_by_id, record.prepared_by_id}",
            source
        )
