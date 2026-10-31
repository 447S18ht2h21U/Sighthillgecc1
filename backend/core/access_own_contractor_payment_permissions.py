"""Contractor-payment-only role gate; defaults to denial.

This gate cannot authorize the broader individual compensation report.
The existing global permission evaluator remains unchanged.
"""

from django.conf import settings

from .access_compensation_report_permissions import (
    OWN_COMPENSATION_PERMISSION,
    require_own_compensation_permission,
)
from .access_own_compensation_candidate_permission import (
    candidate_own_compensation_allowed,
)


def require_own_contractor_payment_permission(actor):
    if (
        getattr(
            settings,
            "VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED",
            False,
        ) is True
        and candidate_own_compensation_allowed(
            actor, OWN_COMPENSATION_PERMISSION
        )
    ):
        return

    require_own_compensation_permission(actor)
