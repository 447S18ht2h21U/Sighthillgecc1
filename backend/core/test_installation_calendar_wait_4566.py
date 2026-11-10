from datetime import datetime, timezone as utc_timezone
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .installation_eligibility import ensure_installation_eligible

EASTERN = ZoneInfo("America/New_York")


class InstallationCalendarWait4566Tests(SimpleTestCase):
    def check_at(self, signed, deadline, now):
        project = SimpleNamespace(pk="fictional-project")
        msr = SimpleNamespace(pk="fictional-msr", status="APPROVED")
        with patch(
            "core.installation_eligibility.require_current_approved_msr",
            return_value=msr,
        ), patch(
            "core.installation_eligibility.verified_signature_time",
            return_value=signed,
        ), patch(
            "core.installation_eligibility.cancellation_deadline",
            return_value=deadline,
        ), patch(
            "core.installation_eligibility.timezone.now",
            return_value=now,
        ), patch(
            "core.installation_payment_readiness.installation_payment_readiness",
            return_value={"payment_ready": True, "explanation": ""},
        ):
            return ensure_installation_eligible(project)

    def test_spring_dst_uses_fifth_eastern_calendar_day(self):
        signed = datetime(2026, 3, 6, 15, 0, tzinfo=EASTERN)
        deadline = datetime(2026, 3, 8, 23, 0, tzinfo=EASTERN)
        before = datetime(2026, 3, 10, 23, 59, tzinfo=EASTERN)
        at = datetime(2026, 3, 11, 0, 0, tzinfo=EASTERN)
        with self.assertRaises(ValidationError):
            self.check_at(signed, deadline, before)
        self.assertIs(self.check_at(signed, deadline, at), True)

    def test_fall_dst_uses_fifth_eastern_calendar_day(self):
        signed = datetime(2026, 10, 30, 14, 0, tzinfo=EASTERN)
        deadline = datetime(2026, 11, 1, 22, 0, tzinfo=EASTERN)
        before = datetime(2026, 11, 3, 23, 59, tzinfo=EASTERN)
        at = datetime(2026, 11, 4, 0, 0, tzinfo=EASTERN)
        with self.assertRaises(ValidationError):
            self.check_at(signed, deadline, before)
        self.assertIs(self.check_at(signed, deadline, at), True)

    def test_later_cancellation_deadline_still_blocks(self):
        signed = datetime(2026, 3, 6, 15, 0, tzinfo=EASTERN)
        deadline = datetime(2026, 3, 12, 13, 30, tzinfo=EASTERN)
        before = datetime(2026, 3, 12, 13, 29, tzinfo=EASTERN)
        at = datetime(2026, 3, 12, 13, 30, tzinfo=EASTERN)
        with self.assertRaises(ValidationError):
            self.check_at(signed, deadline, before)
        self.assertIs(self.check_at(signed, deadline, at), True)

    def test_aware_utc_inputs_preserve_eastern_result(self):
        signed = datetime(2026, 3, 6, 20, 0, tzinfo=utc_timezone.utc)
        deadline = datetime(2026, 3, 9, 0, 0, tzinfo=utc_timezone.utc)
        at = datetime(2026, 3, 11, 4, 0, tzinfo=utc_timezone.utc)
        self.assertIs(self.check_at(signed, deadline, at), True)
