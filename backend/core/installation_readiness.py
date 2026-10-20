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
            "invoice_signed": False,
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

    invoice = CustomerSignatureEvidence.objects.filter(
        msr=msr,
        document_kind=CustomerSignatureEvidence.DocumentKind.INVOICE,
    ).order_by("-created_at").first()

    if contract:
        result["requirements"]["contract_signed"] = True
    else:
        result["blocking_reasons"].append(
            "Verified contract signature evidence is required."
        )

    if invoice:
        result["requirements"]["invoice_signed"] = True
    else:
        result["blocking_reasons"].append(
            "Verified invoice signature evidence is required."
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

    if contract and invoice:
        latest_signature = max(
            contract.signed_at,
            invoice.signed_at,
        ).astimezone(EASTERN)

        eligible_time = latest_signature + timedelta(days=5)

        if timezone.now().astimezone(EASTERN) >= eligible_time:
            result["requirements"]["waiting_period_complete"] = True
        else:
            result["blocking_reasons"].append(
                "Installation waiting period has not expired."
            )

    if msr.snapshot.get("financing_type") == "FINANCED":

        payments = CustomerPayment.objects.filter(
            project=project,
            msr=msr,
            status=CustomerPayment.Status.VERIFIED,
        )

        received = sum(
            (payment.amount for payment in payments),
            Decimal("0.00"),
        )

        adjustments = CustomerPaymentAdjustment.objects.filter(
            payment__in=payments,
            status=CustomerPaymentAdjustment.Status.APPROVED,
        )
        adjusted = sum(
            (item.amount for item in adjustments),
            Decimal("0.00"),
        )

        if received - adjusted >= (
            Decimal(str(msr.snapshot["total_price"]))
            * Decimal("0.50")
        ):
            result["requirements"]["deposit_verified"] = True
        else:
            result["blocking_reasons"].append(
                "Verified 50% deposit is required before installation."
            )

    elif msr.snapshot.get("financing_type") == "NON_FINANCED":
        result["requirements"]["deposit_verified"] = True
    else:
        result["blocking_reasons"].append(
            "Approved MSR requires a valid financing classification."
        )

    result["eligible"] = (
        all(result["requirements"].values())
        and not result["blocking_reasons"]
    )

    return result
