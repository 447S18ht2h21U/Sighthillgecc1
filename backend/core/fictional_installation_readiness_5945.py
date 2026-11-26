"""Isolated fictional installation acceptance assessment.

Never creates operational signature, cancellation, payment,
scheduling or installation-start authority.
"""

import os
import io
import hashlib

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    Project,
    Role,
    CommercialSigningAttempt,
    CommercialSigningObservation,
    CommercialSigningDocument,
)

from .operational_visibility import operational_project_scope
from .installation_payment_readiness import installation_payment_readiness
from .installation_future_date_policy_4565 import assess_future_installation_date
from .installation_waiting_period_policy import assess_waiting_period


PROJECT_ID = "f8a385b5-8e46-4c0c-886a-f8b6d2fc8d05"
MSR_ID = "f555e52f-ae97-4342-982f-dbd42fb0fa62"
PROJECT_CODE = "105-SA-2026-11-23"

ATTEMPT_ID = "e4a9828a-89a8-4099-aeea-d4705fa2c0d5"
OBSERVATION_ID = "1eb6c396-9f65-41a8-82c5-98728e55b713"
ENVELOPE_ID = "d6e2262c-bf37-83e3-80bb-fa0877bf1996"

EASTERN = ZoneInfo("America/New_York")

CUSTOMER_SIGNED_AT = datetime(
    2026, 11, 25, 9, 26, 48, tzinfo=EASTERN
)

# Explicit test fixture, not a legal deadline calculation.
SIMULATED_CANCELLATION_DEADLINE = datetime(
    2026, 12, 9, 0, 0, tzinfo=EASTERN
)

APPROVED_TEST_DATE = date(2026, 12, 10)

SIMULATED_CLOCK = datetime(
    2026, 12, 10, 9, 0, tzinfo=EASTERN
)

EXPECTED_DOCUMENTS = {
    "CONTRACT": 557616,
    "INVOICE": 192391,
    "DOCUSIGN_CERTIFICATE": 271135,
}


def _require_local_environment():
    db = settings.DATABASES["default"]

    expected = (
        Path(__file__).resolve().parents[1]
        / "veridian_browser_acceptance.sqlite3"
    ).resolve()

    if (
        not settings.DEBUG
        or os.environ.get("GECC_DEV") != "1"
        or os.environ.get("VERIDIAN_ENVIRONMENT") != "development"
        or os.environ.get("PGHOST")
        or db["ENGINE"] != "django.db.backends.sqlite3"
        or Path(str(db["NAME"])).resolve() != expected
    ):
        raise PermissionDenied(
            "Fictional installation assessment is unavailable."
        )


def assess_fictional_installation(*, actor, project_id):
    _require_local_environment()

    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or actor.role not in (
            Role.COMPTROLLER,
            Role.INSTALLATION_MANAGER,
        )
        or str(project_id) != PROJECT_ID
    ):
        raise PermissionDenied(
            "Authorized fictional installation review is required."
        )

    project = (
        operational_project_scope(actor)
        .select_related("current_approved")
        .filter(
            pk=PROJECT_ID,
            code=PROJECT_CODE,
            current_approved_id=MSR_ID,
            current_approved__status="APPROVED",
        )
        .exclude(state="CANCELLED")
        .first()
    )

    if (
        project is None
        or project.current_approved.project_id != project.pk
    ):
        raise ValidationError(
            "The approved fictional project is unavailable."
        )

    attempt = CommercialSigningAttempt.objects.get(
        pk=ATTEMPT_ID,
        envelope_id=ENVELOPE_ID,
        state="COMPLETED_RETAINED",
    )

    package = attempt.package
    plan = package.plan

    if (
        str(getattr(plan, "msr_id", "")) != MSR_ID
        or attempt.package_digest != package.digest
    ):
        raise ValidationError(
            "Commercial release does not match the approved MSR."
        )

    observation = CommercialSigningObservation.objects.get(
        pk=OBSERVATION_ID,
        attempt=attempt,
    )

    evidence = observation.evidence

    if (
        evidence.get("account_id") != attempt.account_id
        or evidence.get("envelope_id") != ENVELOPE_ID
        or evidence.get("package_digest") != attempt.package_digest
        or evidence.get("provider_status") != "completed"
        or evidence.get("operational_signature_authorized") is not False
        or evidence.get("installation_authorized") is not False
        or evidence.get("tokens_retained") is not False
    ):
        raise ValidationError(
            "Retained fictional provider evidence is inconsistent."
        )

    completed = parse_datetime(evidence.get("completed_at", ""))

    if (
        completed is None
        or timezone.is_naive(completed)
        or completed < CUSTOMER_SIGNED_AT
        or completed > timezone.now()
    ):
        raise ValidationError(
            "Provider completion timestamp is inconsistent."
        )

    documents = list(
        CommercialSigningDocument.objects.filter(
            attempt=attempt,
            observation=observation,
        )
    )

    if (
        len(documents) != 3
        or {item.kind for item in documents}
           != set(EXPECTED_DOCUMENTS)
    ):
        raise ValidationError(
            "Required signed documents are incomplete."
        )

    expected_hashes = sorted(
        (str(item["document_id"]), item["pdf_sha256"])
        for item in evidence.get("retained_hashes", [])
    )

    actual_hashes = []
    certificate = None

    for document in documents:
        content = bytes(document.content)
        digest = hashlib.sha256(content).hexdigest()

        if (
            not content.startswith(b"%PDF-")
            or len(content) != EXPECTED_DOCUMENTS[document.kind]
            or digest != document.pdf_sha256
        ):
            raise ValidationError(
                "Retained signed document integrity failed."
            )

        actual_hashes.append(
            (str(document.document_id), digest)
        )

        if document.kind == "DOCUSIGN_CERTIFICATE":
            certificate = content

    if sorted(actual_hashes) != expected_hashes:
        raise ValidationError(
            "Provider observation document fingerprints do not match."
        )

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(certificate))
    text = "\n".join(
        page.extract_text() or "" for page in reader.pages
    )

    customer_email = "doug@sighthill.net"
    gecc_email = "whody32@yahoo.com"

    lower = text.casefold()
    start = lower.find(customer_email)
    end = lower.find(gecc_email, start + len(customer_email))

    if start < 0 or end <= start:
        raise ValidationError(
            "Customer certificate section could not be verified."
        )

    customer_section = text[start:end]

    import re

    if (
        "UTC-08:00" not in text
        or not re.search(
            r"Signed:\s*11/25/2026\s+6:26:48\s*AM",
            customer_section,
            re.IGNORECASE,
        )
    ):
        raise ValidationError(
            "Expected customer signing event could not be verified."
        )

    payment = installation_payment_readiness(project)

    waiting = assess_waiting_period(
        verified_contract_signed_at=CUSTOMER_SIGNED_AT,
        verified_cancellation_deadline=SIMULATED_CANCELLATION_DEADLINE,
        now=SIMULATED_CLOCK,
    )

    scheduling = assess_future_installation_date(
        proposed_date=APPROVED_TEST_DATE,
        verified_contract_signed_at=CUSTOMER_SIGNED_AT,
        verified_cancellation_deadline=SIMULATED_CANCELLATION_DEADLINE,
        now=timezone.now(),
    )

    ready = (
        payment["payment_ready"]
        and payment["ceo_exception_valid"]
        and waiting.ready
        and scheduling["normal_date_eligible"]
    )

    return {
        "fictional_acceptance_only": True,
        "project_id": PROJECT_ID,
        "msr_id": MSR_ID,
        "customer_signature_sandbox_verified": True,
        "signed_documents_verified": True,
        "customer_signed_at": CUSTOMER_SIGNED_AT.isoformat(),
        "ceo_payment_exception_verified": payment["ceo_exception_valid"],
        "payment_ready": payment["payment_ready"],
        "cancellation_deadline_simulated": True,
        "simulated_cancellation_deadline":
            SIMULATED_CANCELLATION_DEADLINE.isoformat(),
        "normal_wait_ends_at":
            waiting.contract_wait_ends_at.isoformat(),
        "simulated_clock": SIMULATED_CLOCK.isoformat(),
        "proposed_installation_date":
            APPROVED_TEST_DATE.isoformat(),
        "fictional_scheduling_candidate": ready,
        "operational_signature_verified": False,
        "operational_cancellation_verified": False,
        "operational_scheduling_authorized": False,
        "installation_authorized": False,
        "installation_started": False,
    }