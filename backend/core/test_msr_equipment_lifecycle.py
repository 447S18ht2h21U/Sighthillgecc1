"""Database-backed MSR equipment and Other lifecycle safeguards."""

from copy import deepcopy

from django.test import TestCase

from .models import (
    MSR, AuditEvent, EquipmentCatalogItem,
    ProductCatalogCollection, ProductCatalogMembership,
)
from .services import transition, revise
from . import tests as foundation_tests
from rest_framework.exceptions import PermissionDenied
from .msr_document_source import (
    document_customer_name,
    invoice_other_display,
    invoice_other_notes,
)


class MSREquipmentLifecycleTests(TestCase):
    def setUp(self):
        # Reuse the proven project, account and audit fixtures.
        foundation_tests.FoundationTests.setUp(self)
        # Create real, active test-only catalog identities.
        # Never bypass production catalog-selection validation.
        self.catalog_5697J = ProductCatalogCollection.objects.create(
            name="Goodman Equipment Test Catalog",
            description="Disposable regression fixture",
            created_by=self.manager,
        )
        self.products_5697J = {}
        for model in ("GZV9S", "GZV8S"):
            equipment = EquipmentCatalogItem.objects.create(
                brand="Goodman",
                residential_system_type="Heat Pumps (R-32)",
                model_number=model,
                description="Up to 21.0 SEER2",
                created_by=self.manager,
            )
            ProductCatalogMembership.objects.create(
                catalog=self.catalog_5697J,
                equipment=equipment,
                created_by=self.manager,
            )
            self.products_5697J[model] = equipment

        self.snapshot["customer"] = "Mary Johnson"
        self.snapshot["equipment"] = [{
            "brand": "Goodman",
            "residential_system_type": "Heat Pumps (R-32)",
            "model_number": "GZV9S",
            "description": "Up to 21.0 SEER2",
            "quantity": 1,
            "catalog_id": str(self.catalog_5697J.id),
            "equipment_id": str(self.products_5697J["GZV9S"].id),
        }]
        self.snapshot["other"] = {
            "type": "Reduced Price",
            "amount": "500.00",
            "notes": "Approved customer price reduction",
        }
        self.snapshot["discount"] = "500.00"
        self.snapshot["total_price"] = "9500.00"

    def approve_first(self):
        item = transition(
            self.sales, self.project.pending_id,
            "edit", 0, snapshot=deepcopy(self.snapshot),
        )
        submitted = transition(
            self.sales, item.id, "submit", item.edit_sequence,
        )
        return transition(
            self.manager, submitted.id,
            "approve", submitted.edit_sequence,
        )


    def test_draft_save_before_after_5697J(self):
        original = deepcopy(self.project.pending.snapshot)

        saved = transition(
            self.sales,
            self.project.pending_id,
            "edit",
            0,
            snapshot=deepcopy(self.snapshot),
        )

        first_event = AuditEvent.objects.get(
            entity_id=self.project.id,
            action="msr.edit",
        )

        self.assertEqual(first_event.payload["before"], original)
        self.assertEqual(
            first_event.payload["after"], saved.snapshot
        )
        self.assertEqual(
            first_event.payload["changed_fields"]["customer"]["before"],
            original.get("customer"),
        )
        self.assertEqual(
            first_event.payload["changed_fields"]["customer"]["after"],
            "Mary Johnson",
        )

        updated_snapshot = deepcopy(saved.snapshot)
        updated_snapshot["customer"] = "Mary Johnson-Smith"

        second = transition(
            self.sales,
            saved.id,
            "edit",
            saved.edit_sequence,
            snapshot=updated_snapshot,
        )

        events = list(
            AuditEvent.objects.filter(
                entity_id=self.project.id,
                action="msr.edit",
            ).order_by("sequence")
        )

        self.assertEqual(len(events), 2)

        second_event = events[-1]
        self.assertEqual(
            second_event.payload["before"],
            saved.snapshot,
        )
        self.assertEqual(
            second_event.payload["after"],
            second.snapshot,
        )
        self.assertEqual(
            second_event.payload["changed_fields"]["customer"],
            {
                "before": "Mary Johnson",
                "after": "Mary Johnson-Smith",
            },
        )
        self.assertEqual(
            second_event.payload["version"],
            saved.number,
        )
        self.assertEqual(
            second_event.payload["edit_sequence"],
            second.edit_sequence,
        )

    def test_customer_equipment_and_other_survive_approval(self):
        approved = self.approve_first()
        approved.refresh_from_db()
        self.project.refresh_from_db()

        self.assertEqual(self.project.current_approved_id, approved.id)
        self.assertEqual(document_customer_name(approved.snapshot), "Mary Johnson")
        self.assertEqual(
            approved.snapshot["equipment"][0]["model_number"], "GZV9S",
        )
        self.assertEqual(approved.snapshot["equipment"][0]["brand"], "Goodman")
        self.assertEqual(approved.snapshot["other"]["amount"], "500.00")
        self.assertEqual(invoice_other_display(approved.snapshot), "-500.00")
        self.assertIn(
            "Approved customer price reduction",
            invoice_other_notes(approved.snapshot),
        )

    def test_sales_associate_cannot_approve_own_snapshot(self):
        item = transition(
            self.sales, self.project.pending_id,
            "edit", 0, snapshot=deepcopy(self.snapshot),
        )
        submitted = transition(
            self.sales, item.id, "submit", item.edit_sequence,
        )
        with self.assertRaises(PermissionDenied):
            transition(
                self.sales, submitted.id,
                "approve", submitted.edit_sequence,
            )
        submitted.refresh_from_db()
        self.assertEqual(submitted.status, "SUBMITTED")
        self.project.refresh_from_db()
        self.assertIsNone(self.project.current_approved_id)

    def test_revision_preserves_original_customer_and_equipment(self):
        approved = self.approve_first()
        original = deepcopy(approved.snapshot)

        revised = revise(
            self.sales, self.project.id,
            "Customer requested different system",
            str(approved.id),
        )
        new_data = deepcopy(revised.snapshot)
        new_data["customer"] = "Mary Johnson-Smith"
        new_data["equipment"][0]["model_number"] = "GZV8S"
        new_data["equipment"][0]["catalog_id"] = str(
            self.catalog_5697J.id
        )
        new_data["equipment"][0]["equipment_id"] = str(
            self.products_5697J["GZV8S"].id
        )
        new_data["other"]["notes"] = "Revised approved price reduction"

        edited = transition(
            self.sales, revised.id,
            "edit", revised.edit_sequence, snapshot=new_data,
        )
        submitted = transition(
            self.sales, edited.id,
            "submit", edited.edit_sequence,
        )
        transition(
            self.comptroller, submitted.id,
            "approve", submitted.edit_sequence,
        )

        old_from_db = MSR.objects.get(pk=approved.pk)
        new_from_db = MSR.objects.get(pk=revised.pk)
        self.project.refresh_from_db()

        self.assertEqual(old_from_db.snapshot, original)
        self.assertEqual(document_customer_name(old_from_db.snapshot), "Mary Johnson")
        self.assertEqual(
            old_from_db.snapshot["equipment"][0]["model_number"], "GZV9S",
        )
        self.assertEqual(
            document_customer_name(new_from_db.snapshot), "Mary Johnson-Smith",
        )
        self.assertEqual(
            new_from_db.snapshot["equipment"][0]["model_number"], "GZV8S",
        )
        self.assertEqual(self.project.current_approved_id, revised.id)
        self.assertEqual(revised.number, 2)
        self.assertEqual(revised.source_id, approved.id)

    def test_free_equipment_retained_without_price_deduction(self):
        self.snapshot["other"] = {
            "type": "Free Water Heater",
            "amount": "600.00",
            "notes": "Free Goodman water heater, one unit",
        }
        self.snapshot["discount"] = "0.00"
        self.snapshot["total_price"] = "10000.00"

        approved = self.approve_first()
        approved.refresh_from_db()

        self.assertEqual(approved.snapshot["discount"], "0.00")
        self.assertEqual(
            approved.snapshot["other"]["type"], "Free Water Heater",
        )
        self.assertIsNone(invoice_other_display(approved.snapshot))
        self.assertIn(
            "Free Goodman water heater",
            invoice_other_notes(approved.snapshot),
        )

    def test_msr_workflow_audit_retains_other_and_equipment(self):
        approved = self.approve_first()
        events = AuditEvent.objects.filter(
            entity_id=self.project.id,
            action="msr.approve",
        )
        self.assertEqual(events.count(), 1)
        event = events.get()
        self.assertEqual(event.payload["msr_id"], str(approved.id))
        self.assertEqual(event.payload["snapshot"]["customer"], "Mary Johnson")
        self.assertEqual(
            event.payload["snapshot"]["equipment"][0]["model_number"],
            "GZV9S",
        )
        self.assertEqual(
            event.payload["snapshot"]["other"]["amount"], "500.00",
        )