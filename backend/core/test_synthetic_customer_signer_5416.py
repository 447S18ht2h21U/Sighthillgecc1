"""Synthetic signer authorization security and production isolation tests."""
import os
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from . import tests as foundation
from .models import AuditEvent
from .synthetic_customer_signer_api_5414 import (
    request_authorization,
    approve_authorization,
    status,
)
from .customer_signer_authorization_services import (
    require_approved_customer_signer,
)


@override_settings(DEBUG=True)
class SyntheticSigner5416Tests(TestCase):
    setUp = foundation.FoundationTests.setUp
    edit_submit = foundation.FoundationTests.edit_submit
    approve = foundation.FoundationTests.approve

    def invoke(self, view, actor, payload=None, method="POST"):
        path = f"/api/projects/{self.project.pk}/synthetic-signer/"
        factory = APIRequestFactory()
        if method == "GET":
            request = factory.get(path)
        else:
            request = factory.post(path, payload or {}, format="json")
        force_authenticate(request, user=actor)
        return view(request, project_id=self.project.pk)

    def fictional_context(self):
        from contextlib import ExitStack
        from . import synthetic_customer_signer_api_5414 as module

        stack = ExitStack()
        stack.enter_context(
            patch.object(module, "PROJECT_CODE", self.project.code)
        )
        stack.enter_context(
            patch.dict(
                os.environ,
                {
                    "GECC_DEV": "1",
                    "VERIDIAN_ENVIRONMENT": "development",
                },
            )
        )
        return stack

    def request_test_signer(self):
        return self.invoke(
            request_authorization,
            self.sales,
            {
                "signer_name": "Fictional Test Customer",
                "signer_email": "fictional.customer@example.invalid",
            },
        )

    def test_independent_synthetic_request_and_approval(self):
        self.approve()
        self.project.refresh_from_db()
        with self.fictional_context():
            request_result = self.request_test_signer()
            self.assertEqual(request_result.status_code, 201)
            self.assertTrue(request_result.data["requested"])
            self.assertFalse(request_result.data["approved"])

            result = self.invoke(
                approve_authorization,
                self.manager,
                {"approve": True},
            )
            self.assertEqual(result.status_code, 201)
            self.assertTrue(result.data["approved"])
            self.assertTrue(result.data["synthetic"])

            again = self.invoke(
                approve_authorization,
                self.manager,
                {"approve": True},
            )
            self.assertEqual(again.status_code, 200)

            read = self.invoke(
                status, self.manager, method="GET"
            )
            self.assertEqual(read.status_code, 200)
            self.assertTrue(read.data["approved"])

        self.assertEqual(
            AuditEvent.objects.filter(
                action="customer.synthetic_signer_authorization_requested"
            ).count(),
            1,
        )

    def test_independent_roles_enforced(self):
        self.approve()
        self.project.refresh_from_db()
        with self.fictional_context():
            manager_request = self.invoke(
                request_authorization,
                self.manager,
                {
                    "signer_name": "Fictional Test Customer",
                    "signer_email": "fictional.customer@example.invalid",
                },
            )
            self.assertEqual(manager_request.status_code, 403)

            self.assertEqual(self.request_test_signer().status_code, 201)

            sales_approval = self.invoke(
                approve_authorization,
                self.sales,
                {"approve": True},
            )
            self.assertEqual(sales_approval.status_code, 403)

            comptroller_approval = self.invoke(
                approve_authorization,
                self.comptroller,
                {"approve": True},
            )
            self.assertEqual(comptroller_approval.status_code, 403)

    def test_real_email_and_extra_fields_rejected(self):
        self.approve()
        self.project.refresh_from_db()
        with self.fictional_context():
            response = self.invoke(
                request_authorization,
                self.sales,
                {
                    "signer_name": "Fictional Test Customer",
                    "signer_email": "real.customer@example.com",
                },
            )
            self.assertEqual(response.status_code, 400)

            response = self.invoke(
                request_authorization,
                self.sales,
                {
                    "signer_name": "Fictional Test Customer",
                    "signer_email": "fictional.customer@example.invalid",
                    "driver_license": "DO-NOT-STORE",
                },
            )
            self.assertEqual(response.status_code, 400)

    def test_synthetic_api_denied_outside_debug(self):
        self.approve()
        self.project.refresh_from_db()
        with self.fictional_context(), override_settings(DEBUG=False):
            self.assertEqual(self.request_test_signer().status_code, 403)
            self.assertEqual(
                self.invoke(status, self.manager, method="GET").status_code,
                403,
            )

    def test_synthetic_approval_not_valid_in_production(self):
        self.approve()
        self.project.refresh_from_db()
        with self.fictional_context():
            self.assertEqual(self.request_test_signer().status_code, 201)
            self.assertEqual(
                self.invoke(
                    approve_authorization,
                    self.manager,
                    {"approve": True},
                ).status_code,
                201,
            )

        with override_settings(DEBUG=False):
            with self.assertRaisesMessage(
                ValidationError, "Synthetic test authorization"
            ):
                require_approved_customer_signer(
                    msr=self.project.current_approved,
                    group="COMMERCIAL",
                    signer_name="Fictional Test Customer",
                    signer_email="fictional.customer@example.invalid",
                )
