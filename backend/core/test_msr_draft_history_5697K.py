"""Draft History access and preserved-values checks."""
from copy import deepcopy

from django.test import TestCase
from rest_framework.test import APIClient

from . import tests as foundation
from .models import AuditEvent, Role
from .services import transition


class DraftHistory5697KTests(TestCase):
    def setUp(self):
        foundation.FoundationTests.setUp(self)

    def url(self):
        return f"/api/projects/{self.project.id}/draft-history/"

    def save_draft(self):
        data = deepcopy(self.snapshot)
        data["customer"] = "Fictional Draft History Customer"
        return transition(
            self.sales, self.project.pending_id,
            "edit", 0, snapshot=data,
        )

    def test_authorized_users_see_saved_history(self):
        saved = self.save_draft()
        for actor in (self.sales, self.manager, self.comptroller):
            with self.subTest(role=actor.role):
                self.client.force_authenticate(actor)
                response = self.client.get(self.url())
                self.assertEqual(response.status_code, 200)
                entries = response.json()["entries"]
                self.assertEqual(len(entries), 1)
                self.assertEqual(
                    entries[0]["snapshot"], saved.snapshot
                )
                self.assertEqual(
                    entries[0]["changed_fields"]["customer"]["after"],
                    "Fictional Draft History Customer",
                )
                self.assertTrue(
                    entries[0]["has_explicit_comparison"]
                )

    def test_other_associate_cannot_read_history(self):
        self.save_draft()
        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get(self.url()).status_code, 404
        )

    def test_inactive_account_cannot_read_history(self):
        self.save_draft()
        self.sales.is_active = False
        self.sales.save()
        self.client.force_authenticate(self.sales)
        response = self.client.get(self.url())
        self.assertIn(response.status_code, (401, 403))

    def test_history_endpoint_is_read_only(self):
        self.save_draft()
        before = AuditEvent.objects.count()
        self.client.force_authenticate(self.sales)
        response = self.client.post(
            self.url(), {"snapshot": {}}, format="json"
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_legacy_snapshot_remains_readable(self):
        saved = self.save_draft()
        self.client.force_authenticate(self.sales)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["entries"][0]["version"], saved.number
        )
