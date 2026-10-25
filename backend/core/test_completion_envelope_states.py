"""Fail-closed completion envelope state transition tests."""

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from .completion_envelope_states import require_transition


class CompletionEnvelopeStateTests(SimpleTestCase):
    def test_unsent_cancellation_allowed(self):
        self.assertEqual(require_transition("AUTH_PENDING", "CANCELLED_UNSENT"), "CANCELLED_UNSENT")

    def test_recorded_send_activity_blocks_cancellation(self):
        with self.assertRaises(ValidationError):
            require_transition("AUTH_PENDING", "CANCELLED_UNSENT", "2026-10-21T10:00:00Z")

    def test_network_and_sent_transitions_prohibited(self):
        for next_state in ("NETWORK_STARTED", "SENT_UNCHECKED", "SEND_UNCERTAIN"):
            with self.subTest(next_state=next_state):
                with self.assertRaises(ValidationError):
                    require_transition("AUTH_PENDING", next_state)

    def test_terminal_and_unknown_transitions_prohibited(self):
        for current in ("CANCELLED_UNSENT", "NETWORK_STARTED", "SENT_UNCHECKED", "SEND_UNCERTAIN", "UNKNOWN"):
            with self.subTest(current=current):
                with self.assertRaises(ValidationError):
                    require_transition(current, "CANCELLED_UNSENT")

    def test_repeated_cancellation_rejected(self):
        with self.assertRaises(ValidationError):
            require_transition("CANCELLED_UNSENT", "CANCELLED_UNSENT")
