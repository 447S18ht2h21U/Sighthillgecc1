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
        from unittest.mock import patch as _audit_patch
        audit_patcher = _audit_patch(
            "core.installation_provider_oauth_4979.audit"
        )
        audit_spy = audit_patcher.start()
        self.addCleanup(audit_patcher.stop)
        manager_patcher = patch(
            M + "._screen_intended_manager"
        )
        manager_spy = manager_patcher.start()
        self.addCleanup(manager_patcher.stop)
        f = context()
        f["readback"].audit_events = {
            "auditEvents": [{
                "eventFields": [
                    {"name": "Action", "value": "SyntheticTest"}
                ]
            }]
        }
        f["readback"].audit_events["auditEvents"][0][
            "eventFields"
        ].append({
            "name": "logTime",
            "value": "2026-11-16T12:00:00Z",
        })
        f["readback"].recipient_tabs = {
            "radioGroupTabs": [
                {
                    "groupName": f"inspection_{n}",
                    "radios": [
                        {"value": "Yes", "selected": "true"},
                        {"value": "No", "selected": "false"},
                    ],
                }
                for n in range(1, 6)
            ]
        }
        f["readback"].envelope_summary[
            "completedDateTime"
        ] = "2026-11-16T12:15:00Z"
        f["readback"].recipient_summary = {
            "signers": [{
                "recipientId": "1",
                "status": "completed",
                "name": "Synthetic Installation Manager",
                "email": "synthetic@example.invalid",
                "sentDateTime": "2026-11-16T10:00:00Z",
                "deliveredDateTime": "2026-11-16T11:00:00Z",
                "signedDateTime": "2026-11-16T12:00:00Z",
            }]
        }
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
        manager_spy.assert_called_once_with(
            f["readback"], f["retained"]
        )
        audit_spy.assert_called_once()
        audit_args = audit_spy.call_args.args
        self.assertEqual(
            audit_args[1],
            "installation.inspection_sandbox_readback_bytes_matched",
        )
        audit_payload = audit_args[3]
        self.assertEqual(
            audit_payload["status"],
            "SANDBOX_READBACK_BYTES_MATCHED_SIGNER_UNVERIFIED",
        )
        for key in (
            "provider_signature_verified",
            "signed_date_verified",
            "inspection_findings_verified",
            "trusted_installation_evidence",
            "receipt_issuance_authorized",
            "project_completion_authorized",
        ):
            self.assertIs(audit_payload[key], False)
        from .documents import canonical_hash
        self.assertEqual(
            audit_payload["audit_history_sha256"],
            canonical_hash(f["readback"].audit_events),
        )
        self.assertNotIn("audit_events", audit_payload)
        self.assertNotIn("bearer_token", audit_payload)
        self.assertNotIn("signed_pdf", audit_payload)
        self.assertNotIn("certificate_pdf", audit_payload)

    def test_wrong_signed_pdf_rejected(self):
        from unittest.mock import patch as _audit_patch
        audit_patcher = _audit_patch(
            "core.installation_provider_oauth_4979.audit"
        )
        audit_spy = audit_patcher.start()
        self.addCleanup(audit_patcher.stop)
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
        audit_spy.assert_not_called()

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


class ProviderRecipientScreening5138Tests(TestCase):
    def readback(self):
        return SimpleNamespace(
            envelope_summary={
                "completedDateTime": "2026-11-16T12:15:00Z",
            },
            recipient_summary={
                "signers": [{
                    "recipientId": "1",
                    "status": "completed",
                    "name": "Synthetic Installation Manager",
                    "email": "synthetic@example.invalid",
                    "sentDateTime": "2026-11-16T10:00:00Z",
                    "deliveredDateTime": "2026-11-16T11:00:00Z",
                    "signedDateTime": "2026-11-16T12:00:00Z",
                }]
            },
        )

    def test_consistent_metadata_screened_without_trust(self):
        from .installation_provider_oauth_4979 import (
            _screen_recipient_metadata,
        )
        self.assertIsNone(
            _screen_recipient_metadata(self.readback())
        )

    def test_missing_signed_date_rejected(self):
        from .installation_provider_oauth_4979 import (
            _screen_recipient_metadata,
        )
        value = self.readback()
        del value.recipient_summary["signers"][0]["signedDateTime"]
        with self.assertRaises(ValidationError):
            _screen_recipient_metadata(value)

    def test_wrong_recipient_rejected(self):
        from .installation_provider_oauth_4979 import (
            _screen_recipient_metadata,
        )
        value = self.readback()
        value.recipient_summary["signers"][0]["recipientId"] = "2"
        with self.assertRaises(ValidationError):
            _screen_recipient_metadata(value)

    def test_completion_before_signing_rejected(self):
        from .installation_provider_oauth_4979 import (
            _screen_recipient_metadata,
        )
        value = self.readback()
        value.envelope_summary[
            "completedDateTime"
        ] = "2026-11-16T11:59:59Z"
        with self.assertRaises(ValidationError):
            _screen_recipient_metadata(value)


class IntendedManagerIdentity5142Tests(TestCase):
    MANAGER_ID = "33333333-3333-4333-8333-333333333333"

    def check(self, name="Synthetic Installation Manager",
              email="synthetic@example.invalid",
              manager_present=True, metadata=True):
        from .installation_provider_oauth_4979 import (
            _screen_intended_manager,
        )

        signer = SimpleNamespace(
            pk=self.MANAGER_ID,
            email="synthetic@example.invalid",
            get_full_name=lambda: "Synthetic Installation Manager",
        )
        readback = SimpleNamespace(
            recipient_summary={
                "signers": [{
                    "recipientId": "1",
                    "status": "completed",
                    "name": name,
                    "email": email,
                }]
            }
        )
        retained = SimpleNamespace(
            source_data=(
                {"intended_manager_id": self.MANAGER_ID}
                if metadata else {}
            )
        )

        with patch(M + ".User.objects.filter") as query:
            query.return_value.first.return_value = (
                signer if manager_present else None
            )

            if not metadata:
                with self.assertRaises(ValidationError):
                    _screen_intended_manager(readback, retained)
                query.assert_not_called()
                return

            if not manager_present:
                with self.assertRaises(ValidationError):
                    _screen_intended_manager(readback, retained)
                return

            if name != signer.get_full_name() or (
                email.casefold() != signer.email.casefold()
            ):
                with self.assertRaises(ValidationError):
                    _screen_intended_manager(readback, retained)
                return

            self.assertIsNone(
                _screen_intended_manager(readback, retained)
            )
            query.assert_called_once_with(
                pk=self.MANAGER_ID,
                is_active=True,
                role="INSTALLATION_MANAGER",
            )

    def test_matching_intended_manager_does_not_assert_trust(self):
        self.check()

    def test_different_manager_name_rejected(self):
        self.check(name="Different Installation Manager")

    def test_different_manager_email_rejected(self):
        self.check(email="different@example.invalid")

    def test_inactive_or_missing_manager_rejected(self):
        self.check(manager_present=False)

    def test_missing_retained_manager_identity_rejected(self):
        self.check(metadata=False)


class InspectionTabScreening5144Tests(TestCase):
    def readback(self):
        return SimpleNamespace(
            recipient_tabs={
                "radioGroupTabs": [
                    {
                        "groupName": f"inspection_{n}",
                        "radios": [
                            {"value": "Yes", "selected": "true"},
                            {"value": "No", "selected": "false"},
                        ],
                    }
                    for n in range(1, 6)
                ]
            }
        )

    def screen(self, value):
        from .installation_provider_oauth_4979 import (
            _screen_inspection_response_tabs,
        )
        return _screen_inspection_response_tabs(value)

    def test_five_complete_responses_screen_without_trust(self):
        self.assertIsNone(self.screen(self.readback()))

    def test_missing_inspection_question_rejected(self):
        value = self.readback()
        value.recipient_tabs["radioGroupTabs"].pop()
        with self.assertRaises(ValidationError):
            self.screen(value)

    def test_duplicate_inspection_question_rejected(self):
        value = self.readback()
        value.recipient_tabs["radioGroupTabs"][1][
            "groupName"
        ] = "inspection_1"
        with self.assertRaises(ValidationError):
            self.screen(value)

    def test_no_selected_inspection_answer_rejected(self):
        value = self.readback()
        value.recipient_tabs["radioGroupTabs"][0][
            "radios"
        ][0]["selected"] = "false"
        with self.assertRaises(ValidationError):
            self.screen(value)

    def test_incomplete_tabs_cannot_write_success_audit(self):
        f = context()
        f["readback"].envelope_summary[
            "completedDateTime"
        ] = "2026-11-16T12:15:00Z"
        f["readback"].recipient_summary = {
            "signers": [{
                "recipientId": "1",
                "status": "completed",
                "name": "Synthetic Installation Manager",
                "email": "synthetic@example.invalid",
                "signedDateTime": "2026-11-16T12:00:00Z",
            }]
        }
        f["readback"].recipient_tabs = {
            "radioGroupTabs": []
        }

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
            ),
            patch(M + "._screen_intended_manager"),
            patch(M + ".audit") as audit_spy,
        ):
            with self.assertRaises(ValidationError):
                finish(
                    f["reviewer"],
                    f["challenge"],
                    {"account_id": ACCOUNT, "blockers": []},
                    "synthetic-temporary-token",
                )
            audit_spy.assert_not_called()


class ProviderAuditHistory5147Tests(TestCase):
    def history(self):
        return SimpleNamespace(
            audit_events={
                "auditEvents": [{
                    "eventFields": [
                        {"name": "Action", "value": "SyntheticTest"}
                    ]
                }]
            }
        )

    def screen(self, readback):
        from .installation_provider_oauth_4979 import (
            _screen_provider_audit_history,
        )
        return _screen_provider_audit_history(readback)

    def test_valid_history_does_not_assert_signature(self):
        self.assertIsNone(self.screen(self.history()))

    def test_missing_history_rejected(self):
        readback = self.history()
        readback.audit_events = None
        with self.assertRaises(ValidationError):
            self.screen(readback)

    def test_malformed_event_fields_rejected(self):
        readback = self.history()
        readback.audit_events["auditEvents"][0]["eventFields"] = []
        with self.assertRaises(ValidationError):
            self.screen(readback)

    def test_missing_history_blocks_success_audit(self):
        f = context()
        f["readback"].envelope_summary[
            "completedDateTime"
        ] = "2026-11-16T12:15:00Z"
        f["readback"].recipient_summary = {
            "signers": [{
                "recipientId": "1",
                "status": "completed",
                "name": "Synthetic Installation Manager",
                "email": "synthetic@example.invalid",
                "signedDateTime": "2026-11-16T12:00:00Z",
            }]
        }
        f["readback"].recipient_tabs = {
            "radioGroupTabs": [
                {
                    "groupName": f"inspection_{n}",
                    "radios": [
                        {"value": "Yes", "selected": "true"},
                        {"value": "No", "selected": "false"},
                    ],
                }
                for n in range(1, 6)
            ]
        }

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
            ),
            patch(M + "._screen_intended_manager"),
            patch(M + ".audit") as audit_spy,
        ):
            with self.assertRaises(ValidationError):
                finish(
                    f["reviewer"], f["challenge"],
                    {"account_id": ACCOUNT, "blockers": []},
                    "synthetic-temporary-token",
                )
            audit_spy.assert_not_called()


class ProviderAuditChronology5148Tests(TestCase):
    def evidence(self):
        return SimpleNamespace(
            envelope_summary={
                "completedDateTime": "2026-11-16T12:15:00Z"
            },
            recipient_summary={
                "signers": [{
                    "signedDateTime": "2026-11-16T12:00:00Z"
                }]
            },
            audit_events={
                "auditEvents": [{
                    "eventFields": [
                        {"name": "Action", "value": "SyntheticTest"},
                        {
                            "name": "logTime",
                            "value": "2026-11-16T12:00:00Z",
                        },
                    ]
                }]
            },
        )

    def screen(self, value):
        from .installation_provider_oauth_4979 import (
            _screen_audit_chronology,
        )
        return _screen_audit_chronology(value)

    def test_overlap_does_not_assert_signature(self):
        self.assertIsNone(self.screen(self.evidence()))

    def test_missing_timestamp_rejected(self):
        value = self.evidence()
        value.audit_events["auditEvents"][0]["eventFields"].pop()
        with self.assertRaises(ValidationError):
            self.screen(value)

    def test_timezone_naive_timestamp_rejected(self):
        value = self.evidence()
        value.audit_events["auditEvents"][0][
            "eventFields"
        ][1]["value"] = "2026-11-16T12:00:00"
        with self.assertRaises(ValidationError):
            self.screen(value)

    def test_only_postcompletion_events_rejected(self):
        value = self.evidence()
        value.audit_events["auditEvents"][0][
            "eventFields"
        ][1]["value"] = "2026-11-17T12:00:00Z"
        with self.assertRaises(ValidationError):
            self.screen(value)

    def test_later_document_access_permitted(self):
        value = self.evidence()
        value.audit_events["auditEvents"].append({
            "eventFields": [
                {"name": "Action", "value": "Document Access"},
                {
                    "name": "logTime",
                    "value": "2026-11-17T12:00:00Z",
                },
            ]
        })
        self.assertIsNone(self.screen(value))


class AuditActionConsistency5149Tests(TestCase):
    def readback(self, action="Signed", username="Synthetic Manager"):
        return SimpleNamespace(
            recipient_summary={
                "signers": [{"name": "Synthetic Manager"}]
            },
            audit_events={
                "auditEvents": [{
                    "eventFields": [
                        {"name": "Action", "value": action},
                        {"name": "UserName", "value": username},
                        {"name": "logTime", "value": "2026-11-16T12:00:00Z"},
                    ]
                }]
            },
        )

    def screen(self, value):
        from .installation_provider_oauth_4979 import (
            _screen_audit_action_consistency,
        )
        return _screen_audit_action_consistency(value)

    def test_matching_signed_action_is_not_authentication(self):
        self.assertIsNone(self.screen(self.readback()))

    def test_mismatched_signed_action_rejected(self):
        with self.assertRaises(ValidationError):
            self.screen(self.readback(username="Different Manager"))

    def test_missing_action_rejected(self):
        value = self.readback()
        value.audit_events["auditEvents"][0]["eventFields"].pop(0)
        with self.assertRaises(ValidationError):
            self.screen(value)

    def test_duplicate_action_rejected(self):
        value = self.readback()
        value.audit_events["auditEvents"][0]["eventFields"].append(
            {"name": "Action", "value": "Signed"}
        )
        with self.assertRaises(ValidationError):
            self.screen(value)

    def test_unclassified_action_does_not_imply_signature(self):
        self.assertIsNone(self.screen(
            self.readback(
                action="Printable Copy Delivered",
                username="Other Viewer",
            )
        ))
