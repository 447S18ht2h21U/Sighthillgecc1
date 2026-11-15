from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from core.api import ProjectViewSet


class CustomerOpportunityHistory5036Tests(SimpleTestCase):

    def make_view(self, customer):
        view = ProjectViewSet()
        view.action = "list"
        view.request = SimpleNamespace(
            user=SimpleNamespace(pk=1),
            query_params={"customer": customer},
        )
        scoped = Mock()
        scoped.order_by.return_value = scoped
        scoped.filter.return_value = scoped
        return view, scoped

    @patch("core.api.list_filters")
    @patch("core.api.project_scope")
    @patch("core.api.User.objects.get")
    def test_customer_filter_preserves_project_scope(
        self, get_user, project_scope, list_filters
    ):
        customer = "12345678-1234-1234-1234-123456789abc"
        view, scoped = self.make_view(customer)
        get_user.return_value = SimpleNamespace(is_active=True)
        project_scope.return_value = scoped
        list_filters.return_value = {
            "state": "", "search": "", "sort": "NEWEST"
        }

        self.assertIs(view.get_queryset(), scoped)
        project_scope.assert_called_once()
        scoped.filter.assert_called_once_with(
            customer_id=UUID(customer)
        )

    @patch("core.api.list_filters")
    @patch("core.api.project_scope")
    @patch("core.api.User.objects.get")
    def test_unfiltered_project_list_unchanged(
        self, get_user, project_scope, list_filters
    ):
        view, scoped = self.make_view("")
        get_user.return_value = SimpleNamespace(is_active=True)
        project_scope.return_value = scoped
        list_filters.return_value = {
            "state": "", "search": "", "sort": "NEWEST"
        }

        self.assertIs(view.get_queryset(), scoped)
        scoped.filter.assert_not_called()

    @patch("core.api.project_scope")
    @patch("core.api.User.objects.get")
    def test_invalid_customer_identifier_rejected(
        self, get_user, project_scope
    ):
        view, scoped = self.make_view("invalid-customer")
        get_user.return_value = SimpleNamespace(is_active=True)
        project_scope.return_value = scoped

        with self.assertRaises(ValidationError):
            view.get_queryset()

        scoped.filter.assert_not_called()
