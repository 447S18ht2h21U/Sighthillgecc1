"""Pure test-only validation; no database or external delivery provider."""

import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

from core.invoice_delivery_evidence import assess_delivery_candidate


MSR = "11111111-1111-4111-8111-111111111111"
DOCUMENT = "22222222-2222-4222-8222-222222222222"
PREPARER = "33333333-3333-4333-8333-333333333333"
VERIFIER = "44444444-4444-4444-8444-444444444444"
NOW = datetime(2026, 11, 1, 18, tzinfo=timezone.utc)


class DeliveryEvidenceCandidateTests(unittest.TestCase):
    def sample(self, **overrides):
        values = dict(
            msr_id=MSR,
            document_id=DOCUMENT,
            invoice_sha256="A" * 64,
            recipient_email="customer@example.invalid",
            channel="PROVIDER_EMAIL",
            provider_reference="FICTIONAL-TEST-RECEIPT",
            delivered_at=NOW - timedelta(hours=2),
            verified_by_id=VERIFIER,
            verified_at=NOW - timedelta(hours=1),
            prepared_by_id=PREPARER,
            now=NOW,
        )
        values.update(overrides)
        return values

    def test_complete_candidate_is_still_untrusted(self):
        result = assess_delivery_candidate(**self.sample())
        self.assertFalse(result.trusted_delivery)
        self.assertFalse(result.installation_evidence_accepted)
        self.assertEqual(result.invoice_sha256, "a" * 64)

    def test_bad_msr_and_document_ids_are_rejected(self):
        for field in ("msr_id", "document_id"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                assess_delivery_candidate(**self.sample(**{field: "invalid"}))

    def test_bad_hash_is_rejected(self):
        for digest in ("bad", "x" * 64, None):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                assess_delivery_candidate(**self.sample(invoice_sha256=digest))

    def test_missing_recipient_is_rejected(self):
        for recipient in ("", "no-at-sign", " customer@example.invalid", None):
            with self.subTest(recipient=recipient), self.assertRaises(ValueError):
                assess_delivery_candidate(**self.sample(recipient_email=recipient))

    def test_unapproved_channel_is_rejected(self):
        with self.assertRaises(ValueError):
            assess_delivery_candidate(**self.sample(channel="MANUAL_CLAIM"))

    def test_blank_provider_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            assess_delivery_candidate(**self.sample(provider_reference="  "))

    def test_naive_timestamps_are_rejected(self):
        for field in ("delivered_at", "verified_at"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                assess_delivery_candidate(**self.sample(**{
                    field: datetime(2026, 11, 1, 12)
                }))

    def test_future_timestamps_are_rejected(self):
        for field in ("delivered_at", "verified_at"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                assess_delivery_candidate(**self.sample(**{
                    field: NOW + timedelta(days=1)
                }))

    def test_verification_before_delivery_is_rejected(self):
        with self.assertRaises(ValueError):
            assess_delivery_candidate(**self.sample(
                verified_at=NOW - timedelta(hours=3)
            ))

    def test_same_preparer_and_verifier_are_rejected(self):
        with self.assertRaises(ValueError):
            assess_delivery_candidate(**self.sample(verified_by_id=PREPARER))

    def test_assessment_cannot_be_mutated(self):
        result = assess_delivery_candidate(**self.sample())
        with self.assertRaises(FrozenInstanceError):
            result.installation_evidence_accepted = True

    def test_portal_channel_still_not_trusted(self):
        result = assess_delivery_candidate(**self.sample(channel="VERIFIED_PORTAL"))
        self.assertFalse(result.trusted_delivery)
        self.assertFalse(result.installation_evidence_accepted)


if __name__ == "__main__":
    unittest.main()

# VERIDIAN PROVIDER OBSERVATION PREFLIGHT 4014
from core.invoice_delivery_evidence import preflight_provider_observation


class ProviderObservationPreflightTests(unittest.TestCase):
    def expected(self):
        return dict(
            expected_account_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            expected_envelope_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            expected_document_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            expected_recipient_id="1",
            expected_recipient_email="customer@example.invalid",
        )

    def observation(self):
        return dict(
            account_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            envelope_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            document_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            recipient_id="1",
            recipient_email="customer@example.invalid",
            status="delivered",
        )

    def check(self, change):
        observation = self.observation()
        observation.update(change)
        return preflight_provider_observation(
            observation, **self.expected()
        )

    def test_matching_observation_is_only_structural(self):
        self.assertTrue(self.check({}))

    def test_wrong_account_rejected(self):
        self.assertFalse(self.check({
            "account_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
        }))

    def test_wrong_envelope_rejected(self):
        self.assertFalse(self.check({
            "envelope_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
        }))

    def test_wrong_document_rejected(self):
        self.assertFalse(self.check({
            "document_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
        }))

    def test_wrong_recipient_rejected(self):
        self.assertFalse(self.check({"recipient_id": "2"}))
        self.assertFalse(self.check({
            "recipient_email": "someone-else@example.invalid"
        }))

    def test_other_lifecycle_statuses_rejected(self):
        for status in ("created", "sent", "completed", "voided", "declined"):
            with self.subTest(status=status):
                self.assertFalse(self.check({"status": status}))

    def test_missing_and_malformed_identifiers_rejected(self):
        for value in (None, "", "not-a-uuid"):
            with self.subTest(value=value):
                self.assertFalse(self.check({"envelope_id": value}))

    def test_self_claimed_trust_rejected(self):
        self.assertFalse(self.check({"trusted_delivery": True}))
        self.assertFalse(self.check({
            "installation_evidence_accepted": True
        }))

    def test_missing_observation_rejected(self):
        self.assertFalse(preflight_provider_observation(
            None, **self.expected()
        ))

    def test_structural_match_cannot_authorize_installation(self):
        self.assertTrue(self.check({}))
        candidate = assess_delivery_candidate(
            msr_id="11111111-1111-4111-8111-111111111111",
            document_id="22222222-2222-4222-8222-222222222222",
            invoice_sha256="a" * 64,
            recipient_email="customer@example.invalid",
            channel="PROVIDER_EMAIL",
            provider_reference="FICTIONAL-ONLY",
            delivered_at=NOW,
            verified_by_id=VERIFIER,
            verified_at=NOW,
            prepared_by_id=PREPARER,
            now=NOW,
        )
        self.assertFalse(candidate.trusted_delivery)
        self.assertFalse(candidate.installation_evidence_accepted)
