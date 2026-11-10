"""Candidate unified SOW + expedited-request DocuSign package.

No real provider payload is produced. Document layout, identity authority,
approval evidence, recipient distribution and legal eligibility remain
separate mandatory gates. This pure builder never grants authorization.
"""
from datetime import date
from uuid import UUID

from .expedited_signing_layout_4567 import candidate_layout

DOCUMENTS = (
    ("1", "CUSTOMER_SOW"),
    ("2", "EXPEDITED_SERVICE"),
)

SIGNING_ORDER = (
    "CUSTOMER",
    "INSTALLATION_MANAGER",
    "COMPTROLLER",
)

DISTRIBUTION = (
    "CUSTOMER",
    "CEO",
    "INSTALLATION_MANAGER",
    "COMPTROLLER",
)

# Every requirement must be present before a real envelope can be sent.
# Coordinates for pending fields must be visually confirmed on approved PDFs.
FIELDS = (
    ("sow_proposed_date", "1", "DATE", "PREPOPULATED", True),
    ("sow_customer_initials", "1", "INITIALS", "CUSTOMER", True),
    ("sow_customer_signature", "1", "SIGNATURE", "CUSTOMER", True),
    ("sow_customer_signed_date", "1", "DATE_SIGNED", "CUSTOMER", True),
    ("sow_manager_signature", "1", "SIGNATURE", "INSTALLATION_MANAGER", True),
    ("sow_manager_full_name", "1", "FULL_NAME", "INSTALLATION_MANAGER", True),
    ("sow_manager_signed_date", "1", "DATE_SIGNED", "INSTALLATION_MANAGER", True),
    ("expedited_requested_date", "2", "DATE", "PREPOPULATED", True),
    ("expedited_customer_reason", "2", "MULTILINE_TEXT", "CUSTOMER", True),
    ("expedited_customer_signature", "2", "SIGNATURE", "CUSTOMER", True),
    ("expedited_customer_signed_date", "2", "DATE_SIGNED", "CUSTOMER", True),
    ("expedited_manager_decision", "2", "DECISION", "INSTALLATION_MANAGER", True),
    ("expedited_manager_initials", "2", "INITIALS", "INSTALLATION_MANAGER", True),
    ("expedited_manager_date", "2", "DATE_SIGNED", "INSTALLATION_MANAGER", True),
    ("expedited_comptroller_decision", "2", "DECISION", "COMPTROLLER", True),
    ("expedited_comptroller_initials", "2", "INITIALS", "COMPTROLLER", True),
    ("expedited_comptroller_date", "2", "DATE_SIGNED", "COMPTROLLER", True),
)


def unified_candidate_contract(
    *, reference_root, msr_id, msr_version, snapshot_sha256,
    proposed_date, identities,
):
    """Build only a NOT-SENDABLE candidate from fictional or reviewed values."""
    try:
        canonical_msr = str(UUID(str(msr_id)))
        parsed_date = date.fromisoformat(proposed_date)
    except (TypeError, ValueError, AttributeError):
        raise ValueError("Valid approved-MSR identity and date required.") from None

    if (
        str(msr_id) != canonical_msr
        or type(msr_version) is not int
        or msr_version <= 0
        or type(snapshot_sha256) is not str
        or len(snapshot_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in snapshot_sha256)
        or parsed_date.isoformat() != proposed_date
    ):
        raise ValueError("Approved MSR binding metadata is invalid.")

    if not isinstance(identities, dict):
        raise ValueError("Distinct signer identities are required.")

    parties = {}
    for role in SIGNING_ORDER:
        person = identities.get(role)
        if not isinstance(person, dict):
            raise ValueError("Missing signer identity.")
        name = person.get("name")
        email = person.get("email")
        if (
            type(name) is not str or not name.strip()
            or type(email) is not str or "@" not in email
            or any(ch.isspace() for ch in email)
        ):
            raise ValueError("Signer identity incomplete.")
        parties[role] = {
            "name": name.strip(),
            "email": email.strip().casefold(),
        }

    if len({p["email"] for p in parties.values()}) != len(SIGNING_ORDER):
        raise ValueError("Customer and both independent reviewers must differ.")

    layout = candidate_layout(reference_root)
    mapped = layout["tabs"]
    fields = []
    pending = []

    for key, document_id, field_type, owner, required in FIELDS:
        field = {
            "key": key,
            "document_id": document_id,
            "type": field_type,
            "owner": owner,
            "required": required,
            "visually_approved": False,
        }
        if key in mapped:
            field["candidate_rectangle"] = dict(mapped[key])
        else:
            field["candidate_rectangle"] = None
            pending.append(key)
        if key in ("sow_proposed_date", "expedited_requested_date"):
            field["value"] = parsed_date.isoformat()
            field["locked_to_approved_date"] = True
        elif key == "expedited_customer_reason":
            field["must_be_entered_by_customer"] = True
            field["prepopulated"] = False
        fields.append(field)

    if set(mapped) != {field["key"] for field in fields if field["candidate_rectangle"]}:
        raise ValueError("Unexpected candidate signing tab.")

    return {
        "status": "UNIFIED_ENVELOPE_CANDIDATE_ONLY",
        "msr_id": canonical_msr,
        "msr_version": msr_version,
        "snapshot_sha256": snapshot_sha256,
        "proposed_date": parsed_date.isoformat(),
        "documents": [
            {"document_id": number, "kind": kind, **layout["documents"][kind]}
            for number, kind in DOCUMENTS
        ],
        "envelope_count": 1,
        "signing_order": list(SIGNING_ORDER),
        "signers": parties,
        "required_fields": fields,
        "unplaced_fields": pending,
        "distribution_roles": list(DISTRIBUTION),
        "delivery_evidence_required": True,
        "independent_reviews_required": True,
        "customer_reason_required": True,
        "source_record_verified": False,
        "signing_layout_visually_approved": False,
        "send_authorized": False,
        "provider_signature_verified": False,
        "document_retention_verified": False,
        "legal_eligibility_verified": False,
        "installation_authorized": False,
    }
