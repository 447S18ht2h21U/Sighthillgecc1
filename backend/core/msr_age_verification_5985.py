"""Versioned customer age attestation for the MSR.

Only an authorized assigned Sales Associate can record a new
age attestation through the ordinary MSR editing workflow.

This records the employee's representation that identification
was reviewed. It is not independent proof of customer identity
or the customer's age on a future transaction date.
"""

from datetime import datetime
from uuid import UUID

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Role
from .maryland_cancellation_calendar_5983 import AGE_CATEGORIES


CATEGORY = "customer_age_category"
VERIFIER = "customer_age_verified_by"
VERIFIED_AT = "customer_age_verified_at"
REQUEST = "confirm_customer_age"

AGE_FIELDS = {CATEGORY, VERIFIER, VERIFIED_AT}

IDENTITY_FIELDS = (
    "customer",
    "contact",
    "customer_email",
)


def valid_category(value):
    return isinstance(value, str) and value in AGE_CATEGORIES


def validate_age_fields(snapshot):
    category = snapshot.get(CATEGORY)

    if category is None or category == "":
        if snapshot.get(VERIFIER) or snapshot.get(VERIFIED_AT):
            raise ValidationError({
                CATEGORY: "Incomplete age verification."
            })
        return

    if not valid_category(category):
        raise ValidationError({
            CATEGORY: "Choose age 18-64 or age 65 and older."
        })

    try:
        UUID(str(snapshot[VERIFIER]))

        recorded = datetime.fromisoformat(snapshot[VERIFIED_AT])

        if recorded.utcoffset() is None:
            raise ValueError()

    except (KeyError, ValueError, TypeError, AttributeError):
        raise ValidationError({
            CATEGORY: "Age verification evidence is incomplete."
        })


def require_age_verification(snapshot):
    validate_age_fields(snapshot)

    if not valid_category(snapshot.get(CATEGORY)):
        raise ValidationError({
            CATEGORY:
                "Customer age verification is required before approval."
        })


def normalized_identity(snapshot):
    return tuple(
        str(snapshot.get(key) or "").strip().casefold()
        for key in IDENTITY_FIELDS
    )


def prepare_age_edit(*, actor, project, previous, incoming):
    if not isinstance(incoming, dict):
        raise ValidationError("Invalid commercial snapshot.")

    result = dict(incoming)

    requested = result.pop(REQUEST, False)

    if type(requested) is not bool:
        raise ValidationError({
            CATEGORY: "Invalid age confirmation request."
        })

    category = result.pop(CATEGORY, None)

    # Never trust browser-supplied employee IDs or timestamps.
    result.pop(VERIFIER, None)
    result.pop(VERIFIED_AT, None)

    same_identity = (
        normalized_identity(previous) ==
        normalized_identity(result)
    )

    old_category = previous.get(CATEGORY)

    if requested:
        if (
            actor.role != Role.SALES_ASSOCIATE
            or actor.pk != project.sales_associate_id
            or not actor.is_active
        ):
            raise ValidationError({
                CATEGORY:
                    "The assigned Sales Associate must verify customer age."
            })

        if not valid_category(category):
            raise ValidationError({
                CATEGORY: "Select one of the two age categories."
            })

        if not str(result.get("customer") or "").strip():
            raise ValidationError({
                CATEGORY: "Identify the customer before verifying age."
            })

        result[CATEGORY] = category
        result[VERIFIER] = str(actor.pk)
        result[VERIFIED_AT] = timezone.now().isoformat()

        return result

    if same_identity and valid_category(old_category):
        if category != old_category:
            raise ValidationError({
                CATEGORY:
                    "A changed age category requires fresh verification."
            })

        validate_age_fields(previous)

        for key in AGE_FIELDS:
            result[key] = previous[key]

    elif valid_category(category) and same_identity:
        raise ValidationError({
            CATEGORY: "Verify the customer's identification first."
        })

    # An identity change invalidates an earlier attestation.
    # Unverified drafts may still be saved.

    return result


def clear_age_verification(snapshot):
    result = dict(snapshot)

    for key in AGE_FIELDS | {REQUEST}:
        result.pop(key, None)

    return result
