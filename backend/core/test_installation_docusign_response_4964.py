"""Focused parser and negative-finding tests without provider calls."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .test_installation_signing_findings_4963 import setup
from .installation_docusign_response_4964 import (
    parse_untrusted_docusign_inspection_response,
)

M = "core.installation_docusign_response_4964"


def response(envelope, negative=()):
    """Convert outgoing tab definitions into minimal response-shaped data.

    Outgoing recipient metadata and PDF coordinates are not returned as
    question answers. Keep the response strict and unauthenticated.
    """
    outgoing = envelope.request["recipients"]["signers"][0]["tabs"][
        "radioGroupTabs"
    ]
    groups = []
    for group in outgoing:
        chosen = "NO" if group["groupName"] in negative else "YES"
        groups.append({
            "groupName": group["groupName"],
            "radios": [
                {
                    "value": radio["value"],
                    "selected": (
                        "true" if radio["value"] == chosen else "false"
                    ),
                }
                for radio in group["radios"]
            ],
        })
    return {"radioGroupTabs": groups}


def parse(envelope, tabs):
    return parse_untrusted_docusign_inspection_response(
        envelope=envelope,
        purported_envelope_id="synthetic-envelope-4964",
        recipient_tabs=tabs,
    )


class UnauthenticatedDocuSignResponses4964Tests(TestCase):
    def test_five_yes_responses_unverified(self):
        envelope = setup()
        result = parse(envelope, response(envelope))
        self.assertEqual(len(result.selections), 5)
        self.assertEqual(result.negative_inspection_ids, ())
        self.assertFalse(result.signer_identity_verified)
        self.assertFalse(result.signed_document_verified)
        self.assertFalse(result.completion_authorized)

    def test_no_answers_identified_for_review(self):
        envelope = setup()
        result = parse(
            envelope,
            response(envelope, {"inspection_2", "inspection_4"}),
        )
        self.assertEqual(
            result.negative_inspection_ids,
            ("inspection_2", "inspection_4"),
        )
        self.assertFalse(result.corrective_actions_created)

    def test_missing_response_rejected(self):
        envelope = setup()
        tabs = response(envelope)
        tabs["radioGroupTabs"][0]["radios"][0]["selected"] = "false"
        with self.assertRaises(ValidationError):
            parse(envelope, tabs)

    def test_two_selected_responses_rejected(self):
        envelope = setup()
        tabs = response(envelope)
        tabs["radioGroupTabs"][0]["radios"][1]["selected"] = "true"
        with self.assertRaises(ValidationError):
            parse(envelope, tabs)

    def test_duplicate_question_rejected(self):
        envelope = setup()
        tabs = response(envelope)
        tabs["radioGroupTabs"][1]["groupName"] = "inspection_1"
        with self.assertRaises(ValidationError):
            parse(envelope, tabs)

    def test_extra_survey_response_rejected(self):
        envelope = setup()
        tabs = response(envelope)
        tabs["radioGroupTabs"].append({
            "groupName": "survey_1", "radios": [],
        })
        with self.assertRaises(ValidationError):
            parse(envelope, tabs)

    def test_tampered_unsigned_document_rejected(self):
        envelope = setup()
        envelope.request["documents"][0]["documentBase64"] = "YWJj"
        with self.assertRaises(ValidationError):
            parse(envelope, response(envelope))

    def test_deterministic_but_not_authenticated(self):
        envelope = setup()
        tabs = response(envelope)
        first = parse(envelope, tabs)
        second = parse(envelope, tabs)
        self.assertEqual(first.observation_sha256, second.observation_sha256)
        self.assertFalse(first.live_provider_retrieval_verified)
        self.assertFalse(first.envelope_identity_verified)
        self.assertFalse(first.receipt_issuance_authorized)

    @patch(M + ".settings")
    def test_production_denied(self, settings):
        settings.ENVIRONMENT = "production"
        settings.DEBUG = False
        with self.assertRaises(PermissionDenied):
            parse_untrusted_docusign_inspection_response(
                envelope=None,
                purported_envelope_id="synthetic",
                recipient_tabs={},
            )
