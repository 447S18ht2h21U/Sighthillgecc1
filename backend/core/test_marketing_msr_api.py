"""Database-free Marketing MSR API authorization tests."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from .marketing_msr_api import MarketingMSRViewSet
from .models import Role


class MarketingMSRAPITests(SimpleTestCase):

    def build_view(self, role=Role.MARKETING, method="GET",
                   action="list", authenticated=True):
        view = MarketingMSRViewSet()
        view.action = action
        view.request = SimpleNamespace(
            method=method,
            user=SimpleNamespace(
                pk="test-user",
                is_authenticated=authenticated,
            ),
        )
        return view, role

    def run_scope(self, view, role):
        with (
            patch(
                "core.marketing_msr_api.User.objects.filter"
            ) as user_filter,
            patch(
                "core.marketing_msr_api.MSR.objects.all"
            ) as msrs,
        ):
            user_filter.return_value.values_list.return_value.first.return_value = role
            msrs.return_value.order_by.return_value = "READ_ONLY_SCOPE"
            result = view.get_queryset()
            return result, msrs.called

    def test_only_read_methods_registered(self):
        self.assertEqual(
            MarketingMSRViewSet.http_method_names,
            ["get", "head", "options"],
        )

    def test_no_custom_mutation_actions(self):
        self.assertEqual(MarketingMSRViewSet.get_extra_actions(), [])

    def test_authentication_required(self):
        self.assertIn(
            IsAuthenticated,
            MarketingMSRViewSet.permission_classes,
        )

    def test_active_marketing_list_scope(self):
        view, role = self.build_view()
        result, queried = self.run_scope(view, role)
        self.assertEqual(result, "READ_ONLY_SCOPE")
        self.assertTrue(queried)

    def test_active_marketing_detail_scope(self):
        view, role = self.build_view(action="retrieve")
        result, queried = self.run_scope(view, role)
        self.assertEqual(result, "READ_ONLY_SCOPE")
        self.assertTrue(queried)

    def test_other_roles_cannot_use_marketing_scope(self):
        for role in Role.values:
            if role == Role.MARKETING:
                continue
            with self.subTest(role=role):
                view, _ = self.build_view()
                with self.assertRaises(PermissionDenied):
                    self.run_scope(view, role)

    def test_inactive_marketing_denied(self):
        view, _ = self.build_view()
        with self.assertRaises(PermissionDenied):
            self.run_scope(view, None)

    def test_unauthenticated_denied_before_db_lookup(self):
        view, role = self.build_view(authenticated=False)
        with patch(
            "core.marketing_msr_api.User.objects.filter"
        ) as lookup:
            with self.assertRaises(PermissionDenied):
                view.get_queryset()
            lookup.assert_not_called()

    def test_post_action_denied(self):
        view, role = self.build_view(
            method="POST", action="prepare_signing"
        )
        with self.assertRaises(PermissionDenied):
            self.run_scope(view, role)

    def test_get_unknown_action_denied(self):
        view, role = self.build_view(action="history")
        with self.assertRaises(PermissionDenied):
            self.run_scope(view, role)

    def test_serializer_is_dedicated_to_marketing(self):
        from .marketing_msr_api import MarketingMSRSerializer
        from .api import MSRSerializer

        self.assertIs(
            MarketingMSRViewSet.serializer_class,
            MarketingMSRSerializer,
        )
        self.assertIsNot(MarketingMSRSerializer, MSRSerializer)

    def test_serializer_excludes_unapproved_financial_fields(self):
        from .marketing_msr_api import MarketingMSRSerializer

        source = {
            "customer": "Fixture Customer",
            "base_price": "25000.00",
            "discount": "500.00",
            "total_price": "24500.00",
            "scope": "Fixture installation",
            "gross_profit": "9000.00",
            "net_profit": "7000.00",
            "commission": "1500.00",
            "technician_cost": "800.00",
            "payroll": {"internal": True},
            "internal_secret": "fixture-only",
        }
        record = SimpleNamespace(snapshot=source)

        result = MarketingMSRSerializer().get_snapshot(record)

        for key in (
            "customer",
            "base_price",
            "discount",
            "total_price",
            "scope",
        ):
            self.assertEqual(result[key], source[key])

        for key in (
            "gross_profit",
            "net_profit",
            "commission",
            "technician_cost",
            "payroll",
            "internal_secret",
        ):
            self.assertNotIn(key, result)

        self.assertEqual(record.snapshot, source)

    def test_serializer_defaults_to_empty_snapshot_for_invalid_input(self):
        from .marketing_msr_api import MarketingMSRSerializer

        serializer = MarketingMSRSerializer()
        for value in (None, [], "invalid snapshot", 42):
            with self.subTest(value_type=type(value).__name__):
                self.assertEqual(
                    serializer.get_snapshot(
                        SimpleNamespace(snapshot=value)
                    ),
                    {},
                )