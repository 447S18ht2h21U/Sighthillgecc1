from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from .expedited_service_request_4565 import record_expedited_service_request
from .expedited_service_review_4565 import review_expedited_service_request
from .expedited_manager_decision_4565 import decide_expedited_service_request
from .expedited_chain_readiness_4566 import assess_expedited_chain
from .test_installation_schedule import InstallationScheduleTests


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedChainReadiness4566Tests(TestCase):
    setUp = InstallationScheduleTests.setUp
    make_installation_eligible = InstallationScheduleTests.make_installation_eligible

    def create_chain(self):
        self.make_installation_eligible()
        request = record_expedited_service_request(
            actor=self.manager,
            project_id=self.project.pk,
            proposed_date=timezone.localdate() + timedelta(days=1),
            reason="Fictional customer requests an earlier installation.",
            document_reference="FICTIONAL-REQUEST-4566M",
        )
        review = review_expedited_service_request(
            actor=self.comptroller,
            request_id=request.pk,
            accept_candidate=True,
            review_reason="Independent review of fictional request evidence.",
        )
        decision = decide_expedited_service_request(
            actor=self.manager,
            review_id=review.pk,
            approve=True,
            decision_reason="Manager approval pending actual customer evidence.",
        )
        return request, review, decision

    def test_missing_chain_fails_closed(self):
        result = assess_expedited_chain(self.project)
        self.assertFalse(result["expedited_chain_reviewed"])
        self.assertFalse(result["installation_authorized"])

    def test_complete_chain_records_review_not_installation_authority(self):
        self.create_chain()
        self.project.refresh_from_db()
        result = assess_expedited_chain(self.project)
        self.assertTrue(result["expedited_chain_reviewed"])
        self.assertFalse(result["expedited_authorized"])
        self.assertFalse(result["installation_authorized"])

    def test_missing_manager_decision_fails_closed(self):
        self.make_installation_eligible()
        request = record_expedited_service_request(
            actor=self.manager,
            project_id=self.project.pk,
            proposed_date=timezone.localdate() + timedelta(days=1),
            reason="Fictional customer requests an earlier installation.",
            document_reference="FICTIONAL-REQUEST-NO-DECISION",
        )
        review_expedited_service_request(
            actor=self.comptroller,
            request_id=request.pk,
            accept_candidate=True,
            review_reason="Independent review pending manager approval.",
        )
        self.project.refresh_from_db()
        result = assess_expedited_chain(self.project)
        self.assertFalse(result["expedited_chain_reviewed"])
