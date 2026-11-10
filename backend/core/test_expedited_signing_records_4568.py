
from uuid import uuid4
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from .models import (
    ExpeditedSigningAttempt,
    ExpeditedEnvelopeBinding,
    ExpeditedSigningObservation,
    ExpeditedSigningDocument,
)

ALL = (
    ExpeditedSigningAttempt, ExpeditedEnvelopeBinding,
    ExpeditedSigningObservation, ExpeditedSigningDocument,
)


class ExpeditedSigningRecords4568Tests(SimpleTestCase):
    def test_four_models_registered(self):
        self.assertTrue(all(m._meta.app_label == "core" for m in ALL))

    def test_attempt_has_msr_and_snapshot(self):
        fields = {f.name for f in ExpeditedSigningAttempt._meta.fields}
        self.assertTrue({
            "msr", "initiated_by", "snapshot_sha256",
            "proposed_date", "recipient_manifest", "source_digest",
        }.issubset(fields))

    def test_attempt_source_uniqueness(self):
        self.assertTrue(any(
            c.name == "exp_sign_attempt_source_unique"
            for c in ExpeditedSigningAttempt._meta.constraints
        ))

    def test_envelope_is_bound_to_one_attempt(self):
        self.assertTrue(
            ExpeditedEnvelopeBinding._meta.get_field("attempt").one_to_one
        )

    def test_provider_envelope_id_unique(self):
        self.assertTrue(
            ExpeditedEnvelopeBinding._meta.get_field(
                "provider_envelope_id"
            ).unique
        )

    def test_observations_reference_binding(self):
        self.assertEqual(
            ExpeditedSigningObservation._meta.get_field(
                "binding"
            ).remote_field.model,
            ExpeditedEnvelopeBinding,
        )

    def test_documents_reference_observation(self):
        self.assertEqual(
            ExpeditedSigningDocument._meta.get_field(
                "observation"
            ).remote_field.model,
            ExpeditedSigningObservation,
        )

    def test_document_uniqueness_constraint(self):
        self.assertTrue(any(
            c.name == "exp_sign_document_unique"
            for c in ExpeditedSigningDocument._meta.constraints
        ))

    def test_deletion_rejected(self):
        for model in ALL:
            with self.assertRaises(ValidationError):
                model().delete()

    def test_existing_record_update_rejected(self):
        for model in ALL:
            record = model(id=uuid4())
            record._state.adding = False
            with self.assertRaises(ValidationError):
                record.save()

    def test_no_live_authority_fields(self):
        for model in ALL:
            fields = {f.name for f in model._meta.fields}
            self.assertNotIn("send_authorized", fields)
            self.assertNotIn("installation_authorized", fields)
