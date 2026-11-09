"""Real-model document review integration; isolated SQLite only."""
from copy import deepcopy

from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from django.test import TestCase

from .models import Customer, MSR, Project, User
from .approved_document_msr_binding_4240 import BindingDenied
from .approved_document_record_adapter_4241 import (
    inspect_authorized_document_record,
)


class RealDocumentRecord4243Tests(TestCase):
    @classmethod
    def setUpClass(cls):
        from django.db import connection

        config = settings.DATABASES["default"]
        if (
            config["ENGINE"] != "django.db.backends.sqlite3"
            or config.get("TEST", {}).get("NAME") != ":memory:"
            or connection.vendor != "sqlite"
            or not str(connection.settings_dict["NAME"]).startswith(
                "file:memorydb_"
            )
            or "mode=memory" not in str(connection.settings_dict["NAME"])
        ):
            raise RuntimeError("Only disposable in-memory SQLite is permitted.")
        super().setUpClass()

    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="fictional-comptroller-4243",
            password="test-only-unused-password",
            role="COMPTROLLER",
            initials="FC",
        )
        self.associate = User.objects.create_user(
            username="fictional-associate-4243",
            password="test-only-unused-password",
            role="SALES_ASSOCIATE",
            initials="FA",
        )
        self.outsider = User.objects.create_user(
            username="fictional-outsider-4243",
            password="test-only-unused-password",
            role="SALES_ASSOCIATE",
            initials="FO",
        )

        self.customer = Customer.objects.create(
            legal_name="FICTIONAL CUSTOMER 4243",
            billing_address="100 Fictional Test Lane",
            created_by=self.comptroller,
        )
        self.project = Project.objects.create(
            code="FICTIONAL-PROJECT-4243",
            customer=self.customer,
            location="100 Fictional Test Lane",
            sales_associate=self.associate,
            reviewer=self.comptroller,
            state="ACTIVE",
        )
        self.msr = MSR.objects.create(
            project=self.project,
            number=1,
            status="DRAFT",
            created_by=self.associate,
            prepared_by=self.associate,
            snapshot={
                "customer": "FICTIONAL CUSTOMER 4243",
                "financing_type": "NON_FINANCED",
                "discount": "0.00",
            },
        )
        self.msr.status = "APPROVED"
        self.msr.approved_by = self.comptroller
        self.msr.save(update_fields=["status", "approved_by"])
        self.project.current_approved = self.msr
        self.project.save(update_fields=["current_approved"])

    def review(self, actor=None, msr=None):
        return inspect_authorized_document_record(
            actor=self.comptroller if actor is None else actor,
            project=self.project,
            msr=self.msr if msr is None else msr,
        )

    def test_real_approved_msr_review_succeeds(self):
        report = self.review()
        self.assertEqual(report.msr_id, str(self.msr.pk))
        self.assertEqual(report.project_id, str(self.project.pk))
        self.assertEqual(report.version, 1)
        self.assertEqual(report.financing_type, "NON_FINANCED")
        self.assertTrue(report.review_only)
        self.assertFalse(report.release_authorized)

    def test_real_unauthorized_associate_denied(self):
        with self.assertRaises(PermissionDenied):
            self.review(actor=self.outsider)

    def test_real_draft_msr_denied(self):
        draft = MSR.objects.create(
            project=self.project,
            number=2,
            status="DRAFT",
            created_by=self.associate,
            prepared_by=self.associate,
            snapshot=deepcopy(self.msr.snapshot),
        )
        with self.assertRaises(BindingDenied):
            self.review(msr=draft)

    def test_old_approved_version_denied_after_revision(self):
        successor = MSR.objects.create(
            project=self.project,
            number=2,
            status="DRAFT",
            created_by=self.associate,
            prepared_by=self.associate,
            source=self.msr,
            snapshot=deepcopy(self.msr.snapshot),
        )
        successor.status = "APPROVED"
        successor.approved_by = self.comptroller
        successor.save(update_fields=["status", "approved_by"])
        self.project.current_approved = successor
        self.project.save(update_fields=["current_approved"])

        with self.assertRaises(BindingDenied):
            self.review(msr=self.msr)

        self.assertEqual(self.review(msr=successor).version, 2)

    def test_real_record_review_does_not_modify_data(self):
        original_snapshot = deepcopy(self.msr.snapshot)
        original_state = self.project.state
        report = self.review()

        self.msr.refresh_from_db()
        self.project.refresh_from_db()

        self.assertEqual(self.msr.snapshot, original_snapshot)
        self.assertEqual(self.project.state, original_state)
        self.assertFalse(report.release_authorized)

    def test_cross_project_record_denied(self):
        another = Project.objects.create(
            code="FICTIONAL-OTHER-4243",
            customer=self.customer,
            location="Different Fictional Location",
            sales_associate=self.associate,
            reviewer=self.comptroller,
            state="ACTIVE",
        )
        other_msr = MSR.objects.create(
            project=another,
            number=1,
            status="DRAFT",
            created_by=self.associate,
            prepared_by=self.associate,
            snapshot=deepcopy(self.msr.snapshot),
        )
        with self.assertRaises(BindingDenied):
            self.review(msr=other_msr)