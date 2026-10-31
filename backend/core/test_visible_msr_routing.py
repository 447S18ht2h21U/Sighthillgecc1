"""Test proposed Visible MSR routing without changing production URL configuration."""

from django.test import SimpleTestCase, override_settings
from django.urls import include, path, resolve, reverse
from rest_framework.routers import DefaultRouter

from .visible_msr_api import VisibleMSRViewSet


router = DefaultRouter()
router.register("visible-msrs", VisibleMSRViewSet, basename="visible-msrs")

urlpatterns = [
    path("api/", include(router.urls)),
]


@override_settings(ROOT_URLCONF="core.test_visible_msr_routing")
class VisibleMSRRoutingTests(SimpleTestCase):
    """Temporary, test-only URL configuration."""

    urls = "core.test_visible_msr_routing"

    def test_list_route_resolves_to_correct_viewset(self):
        match = resolve("/api/visible-msrs/")
        self.assertEqual(match.view_name, "visible-msrs-list")
        self.assertIs(match.func.cls, VisibleMSRViewSet)
        self.assertEqual(match.func.actions["get"], "list")

    def test_detail_route_resolves_to_correct_viewset(self):
        url = "/api/visible-msrs/12345678-1234-4234-8234-123456789abc/"
        match = resolve(url)
        self.assertEqual(match.view_name, "visible-msrs-detail")
        self.assertIs(match.func.cls, VisibleMSRViewSet)
        self.assertEqual(match.func.actions["get"], "retrieve")

    def test_reverse_list_route(self):
        self.assertEqual(
            reverse("visible-msrs-list"),
            "/api/visible-msrs/",
        )

    def test_only_read_methods_are_registered(self):
        self.assertEqual(
            VisibleMSRViewSet.http_method_names,
            ["get", "head", "options"],
        )
        match = resolve("/api/visible-msrs/")
        self.assertNotIn("post", match.func.actions)
        self.assertNotIn("put", match.func.actions)
        self.assertNotIn("patch", match.func.actions)
        self.assertNotIn("delete", match.func.actions)

    def test_existing_route_names_are_not_reused(self):
        names = {url.name for url in router.urls if url.name}
        self.assertIn("visible-msrs-list", names)
        self.assertIn("visible-msrs-detail", names)
        self.assertNotIn("msrs-list", names)
        self.assertNotIn("marketing-msrs-list", names)

    def test_proposed_route_has_no_custom_actions(self):
        self.assertEqual(
            VisibleMSRViewSet.get_extra_actions(),
            [],
        )