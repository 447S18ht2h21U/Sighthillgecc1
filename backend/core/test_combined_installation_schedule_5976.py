"""Focused tests for the combined scheduling transaction."""

from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.db import transaction
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .combined_installation_schedule_5976 import (
    CombinedScheduleInput,
    schedule_and_assign,
)


MODULE = "core.combined_installation_schedule_5976"


class CombinedScheduleTests5976(SimpleTestCase):

    def test_empty_technician_selection_rejected(self):
        data = CombinedScheduleInput(data={
            "project": str(uuid4()),
            "scheduled_date": "2026-12-10",
            "technicians": [],
        })
        self.assertFalse(data.is_valid())

    def test_duplicate_technician_selection_rejected(self):
        technician = str(uuid4())
        data = CombinedScheduleInput(data={
            "project": str(uuid4()),
            "scheduled_date": "2026-12-10",
            "technicians": [technician, technician],
        })
        self.assertFalse(data.is_valid())

    def test_multiple_distinct_technicians_accepted(self):
        data = CombinedScheduleInput(data={
            "project": str(uuid4()),
            "scheduled_date": "2026-12-10",
            "technicians": [str(uuid4()), str(uuid4())],
        })
        self.assertTrue(data.is_valid(), data.errors)

    def run_service(self, fail_second=False):
        actor = MagicMock()
        actor.pk = uuid4()

        project = MagicMock()
        project.pk = uuid4()
        project.state = "APPROVED"

        technicians = [MagicMock(), MagicMock()]
        for technician in technicians:
            technician.pk = uuid4()

        schedule = MagicMock()
        schedule.pk = uuid4()

        assignments = [MagicMock(), MagicMock()]
        for assignment, technician in zip(assignments, technicians):
            assignment.pk = uuid4()
            assignment.technical_associate_id = technician.pk

        with (
            patch(MODULE + ".User") as users,
            patch(MODULE + ".Project") as projects,
            patch(MODULE + ".InstallationSchedule") as schedules,
            patch(MODULE + ".ProjectTechnicalAssignment") as records,
            patch(MODULE + ".operational_project_scope") as scope,
            patch(MODULE + ".get_object_or_404") as get_project,
            patch(MODULE + ".create_future_installation_schedule") as create_schedule,
            patch(MODULE + ".create_technical_assignment") as create_assignment,
        ):
            users.objects.filter.return_value.first.return_value = actor
            users.objects.select_for_update.return_value.filter.return_value.order_by.return_value = technicians

            scope.return_value.filter.return_value.exists.return_value = True
            get_project.return_value = project
            schedules.objects.filter.return_value.exists.return_value = False
            records.objects.filter.return_value.select_for_update.return_value = []

            create_schedule.return_value = schedule
            create_assignment.side_effect = (
                [assignments[0], ValidationError("Assignment rejected.")]
                if fail_second else assignments
            )

            arguments = dict(
                actor=actor,
                project_id=project.pk,
                scheduled_date=date(2026, 12, 10),
                technician_ids=[t.pk for t in technicians],
            )

            # Isolate orchestration from the database in these tests.
            # The real service retains its atomic transaction decorator.
            if fail_second:
                with self.assertRaises(ValidationError):
                    schedule_and_assign.__wrapped__(**arguments)
            else:
                result = schedule_and_assign.__wrapped__(**arguments)
                self.assertEqual(len(result["assignments"]), 2)
                self.assertFalse(result["installation_authorized"])
                self.assertFalse(result["installation_started"])

            create_schedule.assert_called_once_with(
                actor=actor,
                project=project,
                scheduled_date=date(2026, 12, 10),
                installation_manager=actor,
            )

            self.assertEqual(create_assignment.call_count, 2)

    def test_existing_services_orchestrated(self):
        self.run_service()

    def test_assignment_failure_propagates(self):
        self.run_service(fail_second=True)
