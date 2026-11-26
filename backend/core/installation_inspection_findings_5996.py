"""Structured installation inspection validation.

This service validates internal inspection findings only.

It does not independently authenticate equipment or distributor
invoice evidence, establish installation acceptance, transmit
a Completion Certificate, or authorize project completion.

Evidence eligibility must be established by the authorized
server-side workflow before a record can be accepted.
"""

from rest_framework.exceptions import ValidationError


POLICY_VERSION = "INSTALLATION-INSPECTION-5996-V1"

ACCEPT = "ACCEPT"
CORRECTIONS_REQUIRED = "CORRECTIONS_REQUIRED"

SATISFIED = "SATISFIED"
UNSATISFIED = "UNSATISFIED"

EQUIPMENT_FINDINGS = (
    "equipment_and_serial_numbers_confirmed",
    "required_materials_confirmed",
    "distributor_invoice_uploaded_and_verified",
)

QUALITY_FINDINGS = (
    "personally_inspected",
    "scope_completed_professionally",
    "technician_delivered_quality_service",
    "job_site_clean",
)

REQUIRED_FINDINGS = (
    EQUIPMENT_FINDINGS + QUALITY_FINDINGS
)

ALLOWED_FIELDS = frozenset(
    REQUIRED_FINDINGS + (
        "customer_impression",
        "inspection_notes",
        "decision",
    )
)


def validate_inspection_findings(
    payload,
    *,
    equipment_evidence_verified,
    materials_evidence_verified,
    distributor_invoice_evidence_verified,
):
    """Validate structured findings against server evidence.

    The three evidence arguments are exclusively server-controlled
    inputs. Browser assertions cannot establish these values.

    A satisfactory inspection requires every finding and a
    satisfactory customer impression. An unsatisfactory result
    requires a documented correction or follow-up explanation.

    Validated findings are not an operational acceptance record.
    """

    if not isinstance(payload, dict):
        raise ValidationError(
            "An installation inspection record is required."
        )

    missing = ALLOWED_FIELDS - set(payload)
    unknown = set(payload) - ALLOWED_FIELDS

    if missing:
        raise ValidationError({
            "inspection": "Missing inspection information.",
            "missing_fields": sorted(missing),
        })

    if unknown:
        raise ValidationError({
            "inspection": "Unexpected inspection information.",
            "unexpected_fields": sorted(unknown),
        })

    for key in REQUIRED_FINDINGS:
        if type(payload[key]) is not bool:
            raise ValidationError({
                key: "Record the actual inspection finding."
            })

    if payload["personally_inspected"] is not True:
        raise ValidationError({
            "personally_inspected":
                "You must personally perform the inspection."
        })

    impression = payload["customer_impression"]

    if impression not in (SATISFIED, UNSATISFIED):
        raise ValidationError({
            "customer_impression":
                "Choose Satisfied or Unsatisfied."
        })

    decision = payload["decision"]

    if decision not in (ACCEPT, CORRECTIONS_REQUIRED):
        raise ValidationError({
            "decision":
                "Choose Accept installation or Request corrections."
        })

    notes = payload["inspection_notes"]

    if not isinstance(notes, str):
        raise ValidationError({
            "inspection_notes": "Enter valid inspection notes."
        })

    notes = notes.strip()

    if len(notes) > 2000:
        raise ValidationError({
            "inspection_notes":
                "Inspection notes cannot exceed 2000 characters."
        })

    evidence = {
        "equipment_and_serial_numbers_confirmed":
            equipment_evidence_verified,

        "required_materials_confirmed":
            materials_evidence_verified,

        "distributor_invoice_uploaded_and_verified":
            distributor_invoice_evidence_verified,
    }

    for key, verified in evidence.items():
        if type(verified) is not bool:
            raise ValidationError({
                key: "Required server evidence could not be verified."
            })

        if payload[key] and not verified:
            raise ValidationError({
                key:
                    "Required supporting evidence must be "
                    "verified before confirming this finding."
            })

    deficiencies = [
        key for key in REQUIRED_FINDINGS
        if not payload[key]
    ]

    customer_concern = impression == UNSATISFIED

    if decision == ACCEPT:
        if deficiencies:
            raise ValidationError({
                "decision":
                    "Resolve all outstanding inspection findings "
                    "before accepting the installation."
            })

        if customer_concern:
            raise ValidationError({
                "decision":
                    "Record and address the customer's concerns "
                    "before accepting the installation."
            })

        if not all(evidence.values()):
            raise ValidationError({
                "decision":
                    "Required supporting evidence is incomplete."
            })

    if decision == CORRECTIONS_REQUIRED or customer_concern:
        if not notes:
            raise ValidationError({
                "inspection_notes":
                    "Describe the required corrections "
                    "or customer concerns."
            })

    return {
        "policy_version": POLICY_VERSION,

        "findings": {
            key: payload[key]
            for key in REQUIRED_FINDINGS
        },

        "customer_impression": impression,
        "inspection_notes": notes,
        "requested_decision": decision,

        "outstanding_findings": deficiencies,
        "customer_follow_up_required": customer_concern,

        "supporting_evidence_confirmed": dict(evidence),

        "findings_validated": True,

        # Validation alone cannot authorize a business action.
        "installation_acceptance_established": False,
        "certificate_transmission_authorized": False,
        "receipt_issuance_authorized": False,
        "project_completion_authorized": False,
    }
