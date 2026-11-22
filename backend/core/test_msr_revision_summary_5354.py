from types import SimpleNamespace
from django.test import SimpleTestCase
from .api import MSRSerializer

class RevisionSummary5354(SimpleTestCase):
    def test_history_fields(self):
        for field in ("source","created_at","created_by_name"):
            self.assertIn(field,MSRSerializer.Meta.fields)

    def test_editor_identity(self):
        person=SimpleNamespace(
            username="manager",
            get_full_name=lambda:"Demo Manager",
        )
        record=SimpleNamespace(created_by=person)
        self.assertEqual(
            MSRSerializer().get_created_by_name(record),
            "Demo Manager",
        )
