"""Database-backed technician assignment ending provenance tests."""
from copy import copy
from datetime import date
from unittest.mock import patch

from .models import AuditEvent, ProjectTechnicalAssignment, Role, User
from .payroll_technical_end_provenance_4298 import (
    _ending_consistent,
    candidate_audited_technical_period,
    audited_technical_period_grants_live_access,
)
from .technical_assignment_services import end_technical_assignment
from .test_payroll_technical_provenance_4296 import (
    DatabaseTechnicalProvenance4296Tests,
)

EARNED = date(2026, 10, 12)


class TechnicalEndProvenance4298Tests(
    DatabaseTechnicalProvenance4296Tests.__bases__[0]
):
    setUp = DatabaseTechnicalProvenance4296Tests.setUp
    assign = DatabaseTechnicalProvenance4296Tests.assign

    def classify(self, earned=EARNED):
        return candidate_audited_technical_period(
            subject_id=self.technician.pk,
            project_id=self.project.pk,
            earned_on=earned,
        )

    def end(self):
        assignment = self.assign()
        end_technical_assignment(self.manager, assignment.pk)
        assignment.refresh_from_db()
        return assignment

    def events(self, assignment):
        creation = AuditEvent.objects.get(
            entity_id=assignment.pk,
            action="TECHNICAL_ASSIGNMENT_CREATED",
        )
        ending = AuditEvent.objects.get(
            entity_id=assignment.pk,
            action="TECHNICAL_ASSIGNMENT_ENDED",
        )
        return creation, ending

    def test_active_assignment_needs_no_ending_event(self):
        self.assign()
        self.assertEqual(self.classify(), Role.TECHNICIAN)
        self.assertFalse(audited_technical_period_grants_live_access())

    def test_real_ended_assignment_has_matching_audit(self):
        assignment = self.end()
        creation, ending = self.events(assignment)
        self.assertTrue(_ending_consistent(assignment, creation, ending))
        self.assertEqual(self.classify(), Role.TECHNICIAN)

    def test_missing_ending_audit_fails_closed(self):
        self.end()
        with patch(
            "core.payroll_technical_end_provenance_4298._ending_events",
            return_value=[],
        ):
            self.assertIsNone(self.classify())

    def test_duplicate_ending_audit_fails_closed(self):
        assignment = self.end()
        _, ending = self.events(assignment)
        with patch(
            "core.payroll_technical_end_provenance_4298._ending_events",
            return_value=[ending, ending],
        ):
            self.assertIsNone(self.classify())

    def test_mismatched_ending_timestamp_and_identity_denied(self):
        assignment = self.end()
        creation, ending = self.events(assignment)

        for key, wrong in (
            ("ended_at", "2020-01-01T00:00:00"),
            ("project_id", str(self.other_project.pk)),
            ("technical_associate_id", str(self.other.pk)),
        ):
            altered = copy(ending)
            altered.payload = {**ending.payload, key: wrong}
            with self.subTest(field=key):
                self.assertFalse(
                    _ending_consistent(assignment, creation, altered)
                )

    def test_wrong_event_order_or_actor_denied(self):
        assignment = self.end()
        creation, ending = self.events(assignment)

        earlier = copy(ending)
        earlier.sequence = creation.sequence
        self.assertFalse(
            _ending_consistent(assignment, creation, earlier)
        )

        missing_actor = copy(ending)
        missing_actor.actor_id = None
        self.assertFalse(
            _ending_consistent(assignment, creation, missing_actor)
        )

    def test_end_before_earning_does_not_classify(self):
        self.end()
        self.assertIsNone(self.classify(earned=date(2027, 1, 1)))

    def test_historical_evidence_survives_current_role_change(self):
        self.end()
        User.objects.filter(pk=self.technician.pk).update(
            role=Role.SALES_ASSOCIATE,
            is_active=False,
        )
        self.assertEqual(self.classify(), Role.TECHNICIAN)
        self.assertFalse(audited_technical_period_grants_live_access(
            subject_id=self.technician.pk,
            viewer_role=Role.INSTALLATION_MANAGER,
        ))