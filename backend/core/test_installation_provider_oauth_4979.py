"""Mocked OAuth handoff and inspection readback acceptance.

No real OAuth, provider network traffic or database writes.
"""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .installation_provider_oauth_4979 import begin, finish, OPERATION

M = "core.installation_provider_oauth_4979"
ACCOUNT = "11111111-1111-4111-8111-111111111111"
ENVELOPE = "22222222-2222-4222-8222-222222222222"
PROJECT = "project-4979"
BINDING = "binding-4979"
RETAINED = "retained-4979"
REVIEWER = 42
PDF = b"%PDF-1.4\n" + b"A" * 150
CERT = b"%PDF-1.4\n" + b"B" * 150


def fixtures():
    from hashlib import sha256

    actor = SimpleNamespace(
        pk=REVIEWER, is_active=True, role="COMPTROLLER"
    )
    project = SimpleNamespace(pk=PROJECT)
    binding = SimpleNamespace(pk=BINDING, digest="a" * 64)
    retained = SimpleNamespace(
        pk=RETAINED,
        signed_pdf=PDF,
        certificate_pdf=CERT,
        signed_pdf_sha256=sha256(PDF).hexdigest(),
        certificate_sha256=sha256(CERT).hexdigest(),
    )
    challenge = SimpleNamespace(
        actor_id=REVIEWER,
        context={
            "operation": OPERATION,
            "project_id": PROJECT,
            "binding_id": BINDING,
            "binding_digest": binding.digest,
            "retained_inspection_id": RETAINED,
            "account_id": ACCOUNT,
            "envelope_id": ENVELOPE,
            "reviewer_id": str(REVIEWER),
            "send_enabled": False,
        },
    )
    readback = SimpleNamespace(
        account_id=ACCOUNT,
        envelope_id=ENVELOPE,
        envelope_summary={
            "envelopeId": ENVELOPE, "status": "completed"
        },
        signed_pdf=PDF,
        certificate_pdf=CERT,
        signed_pdf_sha256=retained.signed_pdf_sha256,
        certificate_sha256=retained.certificate_sha256,
        provider_signature_verified=False,
        completion_authorized=False,
    )
    return actor, project, binding, retained, challenge, readback


def context():
    actor, project, binding, retained, challenge, readback = fixtures()
    return dict(
        reviewer=actor,
        project=project,
        binding=binding,
        retained=retained,
        challenge=challenge,
        readback=readback,
    )


class InspectionOAuthHandoff4979Tests(TestCase):
    def test_callback_uses_only_ephemeral_token_and_matches_pdfs(self):
        f = context()
        with (
            patch(M + "._gate", return_value=f["reviewer"]),
            patch(
                M + "._binding",
                return_value=(
                    f["project"], f["binding"],
                    f["retained"], ACCOUNT, ENVELOPE
                ),
            ),
            patch(
                M + ".retrieve_inspection_sandbox_evidence",
                return_value=f["readback"],
            ) as retrieve,
        ):
            result = finish(
                f["reviewer"],
                f["challenge"],
                {"account_id": ACCOUNT, "blockers": []},
                "synthetic-temporary-token",
            )

        self.assertTrue(result["readback_bytes_match"])
        self.assertFalse(result["provider_signature_verified"])
        self.assertFalse(result["signed_date_verified"])
        self.assertFalse(result["project_completion_authorized"])
        self.assertFalse(result["send_enabled"])
        self.assertNotIn("token", str(result).lower())
        retrieve.assert_called_once()

    def test_wrong_signed_pdf_rejected(self):
        f = context()
        f["readback"].signed_pdf = CERT
        with (
            patch(M + "._gate", return_value=f["reviewer"]),
            patch(M + "._binding", return_value=(
                f["project"], f["binding"],
                f["retained"], ACCOUNT, ENVELOPE
            )),
            patch(
                M + ".retrieve_inspection_sandbox_evidence",
                return_value=f["readback"],
            ),
        ):
            with self.assertRaises(ValidationError):
                finish(
                    f["reviewer"], f["challenge"],
                    {"account_id": ACCOUNT, "blockers": []},
                    "synthetic-token",
                )

    def test_wrong_oauth_operation_rejected(self):
        f = context()
        f["challenge"].context["operation"] = "SANDBOX_SIGNING_SEND"
        with patch(M + "._gate", return_value=f["reviewer"]):
            with self.assertRaises(PermissionDenied):
                finish(
                    f["reviewer"], f["challenge"],
                    {"account_id": ACCOUNT}, "synthetic-token"
                )

    def test_changed_binding_digest_rejected_before_retrieval(self):
        f = context()
        f["challenge"].context["binding_digest"] = "0" * 64
        with (
            patch(M + "._gate", return_value=f["reviewer"]),
            patch(M + "._binding", return_value=(
                f["project"], f["binding"],
                f["retained"], ACCOUNT, ENVELOPE
            )),
            patch(M + ".retrieve_inspection_sandbox_evidence") as fetch,
        ):
            with self.assertRaises(PermissionDenied):
                finish(
                    f["reviewer"], f["challenge"],
                    {"account_id": ACCOUNT, "blockers": []},
                    "synthetic-token",
                )
            fetch.assert_not_called()

    def test_begin_creates_read_only_context(self):
        f = context()
        with (
            patch(M + "._gate", return_value=f["reviewer"]),
            patch(M + "._binding", return_value=(
                f["project"], f["binding"],
                f["retained"], ACCOUNT, ENVELOPE
            )),
            patch(
                M + ".docusign.begin",
                return_value={"authorization_url": "https://example.invalid"},
            ) as oauth,
        ):
            result = begin(
                actor=f["reviewer"],
                project_id=PROJECT,
                binding_id=BINDING,
                session_key="synthetic-local-session",
            )
        self.assertFalse(result["send_enabled"])
        self.assertFalse(result["provider_signature_verified"])
        supplied = oauth.call_args.kwargs["context"]
        self.assertEqual(supplied["operation"], OPERATION)
        self.assertFalse(supplied["send_enabled"])
        self.assertEqual(supplied["binding_id"], BINDING)

    def test_missing_callback_context_rejected(self):
        f = context()
        f["challenge"].context = {}
        with patch(M + "._gate", return_value=f["reviewer"]):
            with self.assertRaises(PermissionDenied):
                finish(f["reviewer"], f["challenge"], {}, "token")

    def test_feature_gate_blocks_unenabled_operation(self):
        f = context()
        with (
            patch(M + ".settings") as settings,
            patch(M + ".os.environ", {}),
        ):
            settings.ENVIRONMENT = "development"
            settings.DEBUG = True
            with self.assertRaises(PermissionDenied):
                begin(
                    actor=f["reviewer"],
                    project_id=PROJECT,
                    binding_id=BINDING,
                    session_key="local-session",
                )

    def test_dispatcher_routes_inspection_without_touching_sender(self):
        from pathlib import Path
        source = Path("core/docusign.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn(
            "if challenge.context.get('operation') == 'SANDBOX_INSPECTION_READ':",
            source,
        )
        self.assertIn(
            "if challenge.context.get('operation') == 'SANDBOX_COMPLETION_READ':",
            source,
        )
        self.assertIn("return finish_inspection(", source)
