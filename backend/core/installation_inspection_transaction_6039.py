"""Integrated development-only installation inspection records.

Retains explicit employee findings and purchasing source references.

An internally recorded inspection does not independently authenticate
physical installation, authorize certificate transmission, issue a
customer Receipt, post financial transactions or complete a project.
"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from .documents import canonical_hash

from .models import (
    User,
    Role,
    ProjectEvidence,
    InstallationSchedule,
    DistributorInvoiceAllocation,
)

from .services import audit

from .distributor_invoice_services_5999 import (
    _project,
    _verify_content,
)

from .installation_equipment_manifest_6038 import (
    build_installation_equipment_manifest,
)

from .installation_inspection_findings_5996 import (
    validate_inspection_findings,
)


INSPECTION_KIND = "INTEGRATED_INSPECTION_6039"


def validate_unit_confirmations(
    *,
    manifest,
    confirmations,
    decision,
):

    if type(confirmations) is not list:

        raise ValidationError(
            "Equipment confirmations must be a list."
        )

    if len(confirmations) > 10000:

        raise ValidationError(
            "Equipment confirmations exceed the review limit."
        )

    if decision not in {
        "ACCEPT",
        "CORRECTIONS_REQUIRED",
    }:

        raise ValidationError(
            "Choose an inspection decision."
        )

    units = {
        unit["unit_id"]: unit
        for unit in manifest["units"]
    }

    if len(units) != len(manifest["units"]):

        raise ValidationError(
            "Equipment inventory contains duplicate identities."
        )

    captured = []

    seen_units = set()

    seen_serials = set()

    for confirmation in confirmations:

        if (
            type(confirmation) is not dict
            or set(confirmation) != {
                "unit_id",
                "serial_number",
                "confirmed",
            }
        ):

            raise ValidationError(
                "Each equipment confirmation must identify "
                "the unit and observed serial number."
            )

        unit_id = confirmation["unit_id"]

        serial = confirmation["serial_number"]

        confirmed = confirmation["confirmed"]

        if (
            type(unit_id) is not str
            or unit_id not in units
            or unit_id in seen_units
        ):

            raise ValidationError(
                "Equipment confirmation references "
                "an invalid or duplicate unit."
            )

        if type(confirmed) is not bool:

            raise ValidationError(
                "Explicit equipment confirmation is required."
            )

        if type(serial) is not str:

            raise ValidationError(
                "Equipment serial number must be text."
            )

        serial = serial.strip()

        if (
            len(serial) > 120
            or any(
                ord(character) < 32
                or ord(character) == 127
                for character in serial
            )
        ):

            raise ValidationError(
                "Equipment serial number is invalid."
            )

        seen_units.add(unit_id)

        unit = units[unit_id]

        selected_source = None

        if confirmed:

            if (
                not serial
                or serial.casefold() in {
                    "unknown",
                    "pending",
                    "none",
                    "n/a",
                    "na",
                    "not available",
                }
            ):

                raise ValidationError(
                    "A confirmed equipment unit requires "
                    "its actual serial number."
                )

            key = serial.casefold()

            if key in seen_serials:

                raise ValidationError(
                    "A serial number cannot identify "
                    "more than one physical unit."
                )

            seen_serials.add(key)

            if unit["purchase_required"]:

                matching_sources = [
                    candidate
                    for candidate in unit["serial_candidates"]
                    if candidate[
                        "serial_number"
                    ].casefold() == key
                ]

                if len(matching_sources) != 1:

                    raise ValidationError(
                        "Confirmed equipment serial does not "
                        "match verified purchasing evidence. "
                        "Request corrections."
                    )

                selected_source = matching_sources[0].copy()

                serial = selected_source["serial_number"]

                assigned_serial = unit[
                    "purchase_serial_number"
                ]

                if (
                    assigned_serial
                    and assigned_serial.casefold() != key
                ):

                    raise ValidationError(
                        "Equipment serial differs from the "
                        "verified purchase assignment."
                    )

        captured.append({
            "unit_id": unit_id,
            "model_number": unit["model_number"],
            "category_of_work": unit["category_of_work"],
            "serial_number": serial,
            "confirmed": confirmed,
            "purchase_required": unit["purchase_required"],
            "purchase_source": selected_source,
        })

    all_confirmed = (
        manifest["available"] is True
        and bool(units)
        and seen_units == set(units)
        and all(
            item["confirmed"] is True
            for item in captured
        )
    )

    if decision == "ACCEPT" and not all_confirmed:

        raise ValidationError(
            "Confirm every required equipment unit "
            "before accepting the installation."
        )

    return {
        "equipment": captured,
        "all_equipment_confirmed": all_confirmed,
    }


def require_inspection_development_environment():

    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or settings.DATABASES["default"]["ENGINE"]
            != "django.db.backends.sqlite3"
    ):

        raise PermissionDenied(
            "Integrated inspection recording "
            "is development-only."
        )


@transaction.atomic
def record_integrated_installation_inspection(
    *,
    actor,
    project_id,
    expected_msr_id,
    expected_snapshot_sha256,
    expected_manifest_sha256,
    equipment_confirmations,
    findings,
    fictional_acceptance_test,
):

    require_inspection_development_environment()

    if fictional_acceptance_test is not True:

        raise ValidationError(
            "This development transaction requires explicit "
            "fictional acceptance-test confirmation."
        )

    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "pk", None)
    ):

        raise PermissionDenied(
            "Authenticated Installation Manager required."
        )

    current = User.objects.select_for_update().filter(
        pk=actor.pk,
        role=Role.INSTALLATION_MANAGER,
        is_active=True,
    ).first()

    if current is None:

        raise PermissionDenied(
            "Active Installation Manager required."
        )

    project, msr = _project(
        current,
        project_id,
    )

    if (
        str(msr.pk) != str(expected_msr_id)
        or canonical_hash(msr.snapshot)
            != expected_snapshot_sha256
    ):

        raise ValidationError(
            "Approved project information changed. "
            "Refresh before recording the inspection."
        )

    schedules = list(
        InstallationSchedule.objects
        .select_for_update()
        .filter(
            project=project,
            installation_manager=current,
            status=InstallationSchedule.Status.COMPLETED,
        )[:2]
    )

    if len(schedules) != 1:

        raise ValidationError(
            "One completed installation schedule "
            "assigned to you is required."
        )

    # Import the existing invoice projection locally,
    # avoiding a module-level circular dependency.

    from .distributor_invoice_api_6006 import _row

    allocations = list(
        DistributorInvoiceAllocation.objects
        .select_for_update()
        .filter(
            project=project,
            msr=msr,
        )
        .select_related("invoice")
        .order_by("invoice__invoice_date", "pk")
    )

    invoice_rows = []

    for allocation in allocations:

        _verify_content(allocation.invoice)

        invoice_rows.append(
            _row(allocation, msr)
        )

    manifest = build_installation_equipment_manifest(
        msr_id=msr.pk,
        snapshot=msr.snapshot,
        invoice_rows=invoice_rows,
    )

    if (
        canonical_hash(manifest)
            != expected_manifest_sha256
    ):

        raise ValidationError(
            "Equipment or purchasing evidence changed. "
            "Refresh and review the inspection again."
        )

    if type(findings) is not dict:

        raise ValidationError(
            "Inspection findings are required."
        )

    decision = findings.get("decision")

    captured = validate_unit_confirmations(
        manifest=manifest,
        confirmations=equipment_confirmations,
        decision=decision,
    )

    # Materials confirmation is an employee observation.
    # No independent materials verification is inferred.

    materials_confirmed = (
        findings.get("required_materials_confirmed")
            is True
        and findings.get("personally_inspected")
            is True
    )

    findings_result = validate_inspection_findings(
        findings,
        equipment_evidence_verified=(
            captured["all_equipment_confirmed"]
        ),
        materials_evidence_verified=(
            materials_confirmed
        ),
        distributor_invoice_evidence_verified=(
            manifest[
                "distributor_purchase_review_complete"
            ]
        ),
    )

    if decision == "ACCEPT":

        if (
            manifest[
                "distributor_purchase_review_complete"
            ] is not True
        ):

            raise ValidationError(
                "Complete distributor invoice verification "
                "before accepting the installation."
            )

    # For this first integrated workflow, prevent duplicate
    # permanent submissions. A controlled correction and
    # reinspection history will be implemented separately.

    if ProjectEvidence.objects.filter(
        msr=msr,
        kind=INSPECTION_KIND,
    ).exists():

        raise ValidationError(
            "An integrated inspection already exists "
            "for this approved project version."
        )

    invoice_evidence = []

    for allocation, row in zip(
        allocations,
        invoice_rows,
    ):

        invoice_evidence.append({
            "invoice_id": str(allocation.invoice_id),
            "allocation_id": str(allocation.pk),
            "invoice_sha256": (
                allocation.invoice.content_sha256
            ),
            "verification_status": (
                row["verification_status"]
            ),
            "equipment_review_recorded": (
                row["equipment_review_recorded"]
            ),
        })

    payload = {
        "purpose": "INTEGRATED_INSTALLATION_INSPECTION",
        "status": (
            "INTERNAL_ACCEPTANCE_CANDIDATE"
            if decision == "ACCEPT"
            else "CORRECTIONS_REQUIRED"
        ),
        "fictional_acceptance_test": True,
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "manifest_sha256": canonical_hash(manifest),
        "schedule_id": str(schedules[0].pk),
        "recorded_by": str(current.pk),
        "recorded_at": timezone.now().isoformat(),
        "equipment": captured["equipment"],
        "all_equipment_confirmed": (
            captured["all_equipment_confirmed"]
        ),
        "invoice_evidence": invoice_evidence,
        "findings": findings.copy(),
        "materials_independently_verified": False,
        "trusted_installation_evidence": False,
        "installation_acceptance_authorized": False,
        "certificate_send_authorized": False,
        "customer_document_release_authorized": False,
        "financial_posting_authorized": False,
        "completion_authorized": False,
    }

    digest = canonical_hash(payload)

    evidence = ProjectEvidence.objects.create(
        msr=msr,
        kind=INSPECTION_KIND,
        created_by=current,
        data=payload,
        digest=digest,
    )

    audit(
        current,
        "installation.integrated_inspection_recorded",
        project.pk,
        {
            "evidence_id": str(evidence.pk),
            "msr_id": str(msr.pk),
            "digest": digest,
            "status": payload["status"],
            "fictional_acceptance_test": True,
            "certificate_send_authorized": False,
        },
    )

    return evidence
