"""Read-only, fictional PDF previews for isolated development.

Never reads project records, generates actual customer documents,
sends notifications, creates document records, or authorizes signatures.
"""
import os
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from .v2_document_mapping_4489 import reference_details
from .remaining_document_population_4518 import fictional_remaining_document
from .completion_address_overlay_4520 import (
    fictional_complete_certificate_address,
)


KINDS = (
    "EXPEDITED_SERVICE",
    "COMPLETION_FINANCED",
    "COMPLETION_NON_FINANCED",
)

ALLOWED_ROLES = frozenset({
    "SALES_ASSOCIATE",
    "SALES_MANAGER",
    "COMPTROLLER",
})

REFERENCE_ROOT = Path(settings.BASE_DIR).parent / "docs/reference/GECC-20261107-final-seven"

FICTIONAL_SNAPSHOT = {
    "customer": "FICTIONAL AVERY SAMPLE",
    "billing_address": "123 Fictional Lane",
    "project_location": "123 Fictional Lane",
    "project_city": "Sample City",
    "project_state": "MD",
    "project_zip": "00000",
    "customer_phone": "555-0100",
    "customer_email": "avery@example.invalid",
    "equipment": [],
    "description_of_work": "New installation",
    "scope": "Fictional HVAC installation.",
    "financing_type": "FINANCED",
    "payment_method": "EFT",
    "base_price": "12000.00",
    "discount": "1000.00",
    "tax": "0.00",
    "total_price": "11000.00",
    "other": {
        "type": "Marketing Promotion",
        "amount": "1000.00",
        "notes": "Fictional retail discount",
    },
}


def development_preview_enabled():
    database = settings.DATABASES["default"]
    return (
        settings.DEBUG is True
        and getattr(settings, "ENVIRONMENT", None) == "development"
        and os.environ.get("GECC_DEV") == "1"
        and os.environ.get("VERIDIAN_ENVIRONMENT", "").lower() == "development"
        and not os.environ.get("PGHOST")
        and database.get("ENGINE") == "django.db.backends.sqlite3"
    )


def generate_fictional_preview(kind):
    if kind not in KINDS:
        raise ValueError("Unsupported fictional document.")

    spec = reference_details(kind)
    original = (REFERENCE_ROOT / spec["filename"]).read_bytes()
    snapshot = dict(FICTIONAL_SNAPSHOT)

    if kind == "COMPLETION_NON_FINANCED":
        snapshot["financing_type"] = "NON_FINANCED"

    if kind.startswith("COMPLETION_"):
        return fictional_complete_certificate_address(
            original, kind, snapshot, "TEST-001", "V1"
        )

    return fictional_remaining_document(
        original, kind, snapshot, "TEST-001", "V1"
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fictional_document_preview(request, kind):
    if not development_preview_enabled():
        return HttpResponseNotFound()

    if request.get_host().split(":")[0] not in (
        "127.0.0.1", "localhost", "testserver"
    ):
        return HttpResponseNotFound()

    actor = request.user
    if not getattr(actor, "is_active", False):
        return HttpResponseNotFound()

    if getattr(actor, "role", None) not in ALLOWED_ROLES:
        return HttpResponseNotFound()

    if kind not in KINDS:
        return HttpResponseNotFound()

    try:
        contents = generate_fictional_preview(kind)
    except (ValueError, OSError, KeyError):
        # Fail closed. Do not expose filesystem or customer information.
        return HttpResponseNotFound()

    response = HttpResponse(contents, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="FICTIONAL-{kind}-PREVIEW.pdf"'
    )
    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
