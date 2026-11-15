from types import SimpleNamespace

from django.test import SimpleTestCase

from core.marketing_msr_api import MarketingMSRSerializer
from core.visible_msr_api import VisibleMSRViewSet
from core.marketing_msr_api import MarketingMSRViewSet


class MSRProjectCode5064Tests(SimpleTestCase):

    def test_project_code_uses_authoritative_project_relation(self):
        serializer = MarketingMSRSerializer()
        field = serializer.fields["project_code"]

        record = SimpleNamespace(
            project=SimpleNamespace(code="101-SA-2026-10-05")
        )

        self.assertEqual(
            field.get_attribute(record),
            "101-SA-2026-10-05",
        )
        self.assertTrue(field.read_only)

    def test_both_directories_share_project_code_serializer(self):
        self.assertIs(
            VisibleMSRViewSet.serializer_class,
            MarketingMSRSerializer,
        )
        self.assertIs(
            MarketingMSRViewSet.serializer_class,
            MarketingMSRSerializer,
        )
        self.assertIn(
            "project_code",
            MarketingMSRSerializer.Meta.fields,
        )
