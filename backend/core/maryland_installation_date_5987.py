"""Maryland installation-date assessment.

Read-only calculation based on an approved MSR and established
commercial evidence. Does not authorize installation or replace
existing scheduling, payment, or signature protections.
"""

from datetime import datetime

from rest_framework.exceptions import ValidationError

from .models import CustomerSignatureEvidence

from .installation_eligibility import (
    require_current_approved_msr,
    verified_signature_time,
    cancellation_deadline,
)

from .msr_age_verification_5985 import (
    CATEGORY,
    VERIFIED_AT,
    require_age_verification,
)

from .maryland_cancellation_calendar_5983 import (
    EASTERN,
    date_after_established_deadlines,
)


def assess_maryland_installation_date(project):
    result = {
        "status": "NOT_ESTABLISHED",
        "policy": "MARYLAND_HOME_IMPROVEMENT",
        "contract_signed_at": None,
        "transaction_date": None,
        "required_business_days": None,
        "effective_cancellation_deadline": None,
        "earliest_normal_installation_date": None,
        "blocking_reasons": [],
        "installation_authorized": False,
        "expedited_authorized": False,
    }

    try:
        msr = require_current_approved_msr(project)

        if str(
            msr.snapshot.get("project_state") or ""
        ).strip().upper() != "MD":
            raise ValidationError(
                "Maryland installation jurisdiction is not established."
            )

        require_age_verification(msr.snapshot)

        signed_at = verified_signature_time(
            msr,
            CustomerSignatureEvidence.DocumentKind.CONTRACT,
        )

        if (
            not isinstance(signed_at, datetime)
            or signed_at.utcoffset() is None
        ):
            raise ValidationError(
                "Authenticated Contract signature time is required."
            )

        result["contract_signed_at"] = (
            signed_at.astimezone(EASTERN).isoformat()
        )

        verified_at = datetime.fromisoformat(
            msr.snapshot[VERIFIED_AT]
        )

        if verified_at > signed_at:
            raise ValidationError(
                "Customer age verification must precede Contract signing."
            )

        if (
            verified_at.astimezone(EASTERN).date()
            != signed_at.astimezone(EASTERN).date()
        ):
            raise ValidationError(
                "Customer age category requires confirmation "
                "for the actual transaction date."
            )

        established_deadline = cancellation_deadline(msr)

        # Signature time is not automatically the legal transaction date.
        # Until the transaction date and required cancellation notices
        # are authenticated, the calculation remains provisional.

        calculation = date_after_established_deadlines(
            transaction_date=signed_at.astimezone(EASTERN).date(),
            age_category=msr.snapshot[CATEGORY],
            independently_verified_deadline=established_deadline,
        )

        result.update({
            "status": "PROVISIONAL",
            "required_business_days":
                calculation["required_business_days"],
            "provisional_transaction_date":
                calculation["transaction_date"],
            "provisional_cancellation_deadline":
                calculation["effective_deadline"],
            "provisional_earliest_installation_date":
                calculation["earliest_normal_installation_date"],
        })

        result["blocking_reasons"].append(
            "Authenticate the legal transaction date and required "
            "customer cancellation notices before establishing "
            "the earliest normal installation date."
        )

    except ValidationError as exc:
        detail = exc.detail

        if isinstance(detail, (list, tuple)):
            result["blocking_reasons"].extend(
                str(item) for item in detail
            )
        else:
            result["blocking_reasons"].append(str(detail))

    except (ValueError, TypeError, KeyError, OverflowError):
        result["blocking_reasons"].append(
            "The installation date evidence could not be validated."
        )

    return result
