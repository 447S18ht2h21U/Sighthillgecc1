from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .models import (
    CustomerPayment,
    CustomerPaymentAdjustment,
    CustomerSignatureEvidence,
    ProjectEvidence,
)
from rest_framework.exceptions import ValidationError
from .installation_eligibility import parse_verified_cancellation_deadline
from .rules import EASTERN


def installation_readiness(project):
    result = {
        "eligible": False,
        "requirements": {
            "approved_msr": False,
            "contract_signed": False,
            "cancellation_complete": False,
            "waiting_period_complete": False,
            "deposit_verified": False,
        },
        "blocking_reasons": [],
    }

    msr = project.current_approved

    if msr is None or msr.status != "APPROVED":
        result["blocking_reasons"].append(
            "Installation requires a current approved MSR."
        )
        return result

    result["requirements"]["approved_msr"] = True

    contract = CustomerSignatureEvidence.objects.filter(
        msr=msr,
        document_kind=CustomerSignatureEvidence.DocumentKind.CONTRACT,
    ).order_by("-created_at").first()

    if contract:
        result["requirements"]["contract_signed"] = True
    else:
        result["blocking_reasons"].append(
            "Verified contract signature evidence is required."
        )

    cancellation = ProjectEvidence.objects.filter(
        msr=msr,
        kind="CANCELLATION_DEADLINE",
    ).order_by("-created_at", "-id").first()

    if cancellation and cancellation.data.get("verified") is True and cancellation.data.get("deadline"):
        try:
            deadline = parse_verified_cancellation_deadline(cancellation.data["deadline"])
        except ValidationError:
            deadline = None
        if deadline is None:
            result["blocking_reasons"].append("Valid cancellation deadline with UTC offset is required.")
        elif timezone.now().astimezone(EASTERN) >= deadline:
            result["requirements"]["cancellation_complete"] = True
        else:
            result["blocking_reasons"].append("Cancellation deadline has not expired.")
    else:
        result["blocking_reasons"].append(
            "Verified cancellation deadline evidence is required."
        )

    if contract:
        eligible_time = contract.signed_at.astimezone(EASTERN) + timedelta(days=5)

        if timezone.now().astimezone(EASTERN) >= eligible_time:
            result["requirements"]["waiting_period_complete"] = True
        else:
            result["blocking_reasons"].append(
                "Installation waiting period has not expired."
            )

    from .installation_payment_readiness import installation_payment_readiness

    try:
        payment = installation_payment_readiness(project)
    except ValidationError as exc:
        detail = exc.detail
        if isinstance(detail, (list, tuple)):
            result["blocking_reasons"].extend(str(item) for item in detail)
        else:
            result["blocking_reasons"].append(str(detail))
    else:
        if payment["payment_ready"]:
            result["requirements"]["deposit_verified"] = True
        else:
            result["blocking_reasons"].append(payment["explanation"])

    result["eligible"] = (
        all(result["requirements"].values())
        and not result["blocking_reasons"]
    )

    return result
