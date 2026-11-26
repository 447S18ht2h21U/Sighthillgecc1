"""Employee access to fictional Completion Certificate draft creation.

No sending endpoint or operational completion authority.
"""

import os

from django.db import transaction

from rest_framework.decorators import (
    api_view,
    permission_classes,
    parser_classes,
)

from rest_framework.parsers import JSONParser

from rest_framework.permissions import IsAuthenticated

from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from rest_framework.response import Response

from . import docusign

from .documents import canonical_hash

from .distributor_invoice_api_6006 import _reader

from .completion_certificate_provider_6063 import (
    FLAG,
    PROJECT_ID,
    PACKAGE_ID,
    PACKAGE_DIGEST,
    RESERVATION_KIND,
    RESULT_KIND,
    OBSERVATION_KIND,
    current_package,
    single_evidence,
    uuid_value,
    begin,
)


def private(data):

    response = Response(data)

    response["Cache-Control"] = "private, no-store"

    response["Referrer-Policy"] = "no-referrer"

    response["X-Content-Type-Options"] = "nosniff"

    return response


def checked_record(record, msr):

    if record is None:

        return None

    if (
        record.msr_id != msr.pk
        or type(record.data) is not dict
        or canonical_hash(record.data) != record.digest
        or record.data.get("package_digest") != PACKAGE_DIGEST
        or record.data.get("send_authorized") is not False
        or record.data.get("signed") is not False
        or record.data.get("completion_authorized") is not False
    ):

        raise ValidationError(
            "Provider tracking evidence requires reconciliation."
        )

    return record.data


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def completion_certificate_provider(request, project_id):

    if str(project_id) != PROJECT_ID:

        raise PermissionDenied(
            "This operation is restricted to the fictional test project."
        )

    actor = _reader(request)

    if request.method == "POST":

        required = {
            "expected_package_id",
            "expected_package_digest",
            "confirmed",
        }

        if (
            type(request.data) is not dict
            or set(request.data) != required
        ):

            raise ValidationError(
                "Explicit fictional draft confirmation required."
            )

        if request.data["confirmed"] is not True:

            raise ValidationError(
                "Confirm creation of an unsent sandbox draft."
            )

        result = begin(
            actor=actor,
            session_key=request.session.session_key,
            project_id=project_id,
            **request.data,
        )

        return private(result)

    with transaction.atomic():

        project, msr, package, certificate, payload = (
            current_package(actor)
        )

        reservation = single_evidence(
            project,
            RESERVATION_KIND,
        )

        result = single_evidence(
            project,
            RESULT_KIND,
        )

        observation = single_evidence(
            project,
            OBSERVATION_KIND,
        )

        r = checked_record(reservation, msr)

        d = checked_record(result, msr)

        o = checked_record(observation, msr)

        state = "NO_DRAFT"

        envelope_id = None

        reconciliation_required = False

        metadata_verified = False

        if r is None:

            if d is not None or o is not None:

                raise ValidationError(
                    "Orphaned provider tracking evidence."
                )

        else:

            if (
                r.get("state") != "PROVIDER_OUTCOME_UNKNOWN"
                or r.get("project_id") != PROJECT_ID
                or r.get("msr_id") != str(msr.pk)
                or r.get("package_id") != PACKAGE_ID
                or r.get("certificate_id") != str(certificate.pk)
                or r.get("certificate_digest") != certificate.digest
                or r.get("pdf_sha256")
                    != certificate.data["pdf_sha256"]
                or r.get("reserved_by")
                    != str(reservation.created_by_id)
                or r.get("payload_digest")
                    != canonical_hash(payload)
            ):

                raise ValidationError(
                    "Draft reservation binding requires review."
                )

            state = "PROVIDER_OUTCOME_UNKNOWN"

            reconciliation_required = True

            if d is None:

                if o is not None:

                    raise ValidationError(
                        "Provider result is missing."
                    )

            else:

                if (
                    d.get("reservation_id")
                        != str(reservation.pk)
                    or d.get("reservation_digest")
                        != reservation.digest
                    or d.get("account_id") != r.get("account_id")
                    or result.created_by_id
                        != reservation.created_by_id
                    or d.get("state")
                        != "CREATED_UNVALIDATED"
                ):

                    raise ValidationError(
                        "Provider result binding requires review."
                    )

                envelope_id = uuid_value(
                    d.get("envelope_id")
                )

                state = "CREATED_UNVALIDATED"

                if o is not None:

                    if (
                        o.get("result_id") != str(result.pk)
                        or o.get("result_digest") != result.digest
                        or o.get("envelope_id") != envelope_id
                        or o.get("account_id") != d.get("account_id")
                        or o.get("state")
                            != "DRAFT_METADATA_VALIDATED"
                        or d.get("provider_status") != "created"
                        or observation.created_by_id
                            != result.created_by_id
                        or o.get("checks") != {
                            "recipient_metadata_verified": True,
                            "tab_metadata_verified": True,
                            "document_inventory_verified": True,
                            "provider_pdf_content_verified": False,
                            "visual_layout_verified": False,
                        }
                    ):

                        raise ValidationError(
                            "Provider observation binding requires review."
                        )

                    state = "DRAFT_METADATA_VALIDATED"

                    metadata_verified = True

                    reconciliation_required = False

        config = docusign.configuration()

        enabled = os.environ.get(FLAG) == "1"

        other_sending_enabled = any(
            os.environ.get(name) == "1"
            for name in (
                "GECC_COMMERCIAL_SANDBOX_SEND_ENABLED",
                "GECC_SANDBOX_SIGNING_SEND_ENABLED",
            )
        )

        blockers = list(config["blockers"])

        if not enabled:

            blockers.append(
                "Sandbox draft creation is disabled."
            )

        if other_sending_enabled:

            blockers.append(
                "Other sandbox sending operations must be disabled."
            )

        return private({
            "project_id": str(project.pk),
            "msr_id": str(msr.pk),
            "package_id": str(package.pk),
            "package_digest": package.digest,
            "certificate_id": str(certificate.pk),
            "pdf_sha256": certificate.data["pdf_sha256"],
            "recipient": package.data["recipient"]["email"],
            "state": state,
            "envelope_id": envelope_id,
            "metadata_verified": metadata_verified,
            "visual_layout_verified": False,
            "provider_pdf_content_verified": False,
            "reconciliation_required": reconciliation_required,
            "create_available": (
                state == "NO_DRAFT"
                and not blockers
            ),
            "configuration_blockers": blockers,
            "fictional": True,
            "send_authorized": False,
            "completion_authorized": False,
            "automatic_retry_allowed": False,
        })
