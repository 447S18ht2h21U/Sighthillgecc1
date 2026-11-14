from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .receipt_graph_project_gate_4929 import (
    prepare_project_graph_receipt_preview,
)


MODULE = "core.receipt_graph_project_gate_4929"


def project():
    msr = SimpleNamespace(
        pk="msr-4929",
        project_id="project-4929",
        status="APPROVED",
        snapshot={"customer_email": "synthetic@example.invalid"},
    )
    return SimpleNamespace(
        pk="project-4929",
        current_approved=msr,
        current_approved_id=msr.pk,
        state="ACTIVE",
    )


class GraphProjectGateTests(TestCase):

    def test_missing_actor_denied(self):
        with self.assertRaises(PermissionDenied):
            prepare_project_graph_receipt_preview(
                actor=None,
                project_id="project-4929",
                document_id="document-4929",
            )

    @patch(MODULE + ".User.objects")
    def test_inactive_actor_denied(self, users):
        users.filter.return_value.first.return_value = None
        with self.assertRaises(PermissionDenied):
            prepare_project_graph_receipt_preview(
                actor=SimpleNamespace(pk="actor"),
                project_id="project-4929",
                document_id="document-4929",
            )

    @patch(MODULE + ".Project.objects")
    @patch(MODULE + ".User.objects")
    def test_cancelled_project_denied(self, users, projects):
        users.filter.return_value.first.return_value = (
            SimpleNamespace(role="COMPTROLLER")
        )
        candidate = project()
        candidate.state = "CANCELLED"
        projects.select_related.return_value.get.return_value = candidate
        with self.assertRaises(ValidationError):
            prepare_project_graph_receipt_preview(
                actor=SimpleNamespace(pk="actor"),
                project_id="project-4929",
                document_id="document-4929",
            )

    @patch(MODULE + ".assess_final_receipt_release_preflight")
    @patch(MODULE + ".assess_final_receipt_issuance_boundary")
    @patch(MODULE + ".Project.objects")
    @patch(MODULE + ".User.objects")
    def test_existing_issuance_denial_blocks_preview(
        self, users, projects, issuance, release
    ):
        users.filter.return_value.first.return_value = (
            SimpleNamespace(role="COMPTROLLER")
        )
        projects.select_related.return_value.get.return_value = project()
        issuance.return_value = SimpleNamespace(
            project_id="project-4929",
            msr_id="msr-4929",
            customer_receipt_issuance_authorized=False,
            trusted_installation_evidence=False,
        )
        release.return_value = SimpleNamespace(
            project_id="project-4929",
            msr_id="msr-4929",
            final_receipt_issuance_authorized=False,
            trusted_installation_evidence=False,
        )
        with patch(
            MODULE + ".prepare_graph_receipt_preview"
        ) as graph:
            with self.assertRaises(PermissionDenied):
                prepare_project_graph_receipt_preview(
                    actor=SimpleNamespace(pk="actor"),
                    project_id="project-4929",
                    document_id="document-4929",
                )
            graph.assert_not_called()
