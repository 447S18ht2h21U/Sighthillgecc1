"""November 7 V2 document reference and MSR projection foundation.

Development-only pure mapping. No release, provider calls, database
writes, legal eligibility decisions, or historical document changes.
"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from .msr_document_source import customer_document_data


REFERENCE_FILES = {
    "CUSTOMER_SOW": ("GECC Project Scope of Work 20261107v2.pdf", "E838AD22D5228205E92AD0ED4C73AFA6DCDE5896E8E0462EA1D4466276030BD5"),
    "AGREEMENT": ("GECC Project SOW Agreement Maryland 20261107v2.pdf", "2AD6DD5085F2DE012A51A3B77E902DA631A6812C9F322BFD8B6055A915E078BD"),
    "INVOICE": ("GECC Invoice 20261107v4.pdf", "8665F93C928F146BC3371DEC7153ADA731F39493BE00B240D6B610C9E5BFEB6E"),
    "EXPEDITED_SERVICE": ("GECC Expedite Service Request 20261107v2.pdf", "2E822C7C946FD9F909544DF7AE73925CA7E1BE7D33D8FF006CD61FA3D97273FF"),
    "RECEIPT": ("GECC Receipt 20261107v4-survey-corrected.pdf", "02F94BA72A5FAE593278A2C781659FC97B0001A692216C8780D066C38155E300"),
    "COMPLETION_FINANCED": ("GECC FINANCED Completion Certificate 20261107v2.pdf", "9158571E4663A52D614058860F4455869F5CBE7FA53B03C9250CC48717CF18A4"),
    "COMPLETION_NON_FINANCED": ("GECC NOT-FINANCED Completion Certificate 20261107v2.pdf", "DF0AAC2BA59868ECCDE183537B3D86436FB23E2E994A878C102D76BADDED818B"),
}

DOCUMENT_STAGES = {
    "CUSTOMER_SOW": "SALE",
    "AGREEMENT": "SALE",
    "INVOICE": "SALE",
    "EXPEDITED_SERVICE": "CONDITIONAL_PREINSTALLATION",
    "RECEIPT": "POST_INSTALLATION",
    "COMPLETION_FINANCED": "POST_INSTALLATION",
    "COMPLETION_NON_FINANCED": "POST_INSTALLATION",
}

EQUIPMENT_KINDS = frozenset({
    "CUSTOMER_SOW", "INVOICE", "RECEIPT",
})


def reference_details(kind):
    if kind not in REFERENCE_FILES:
        raise ValueError("Unsupported V2 document kind.")
    filename, fingerprint = REFERENCE_FILES[kind]
    return {
        "kind": kind,
        "filename": filename,
        "sha256": fingerprint,
        "stage": DOCUMENT_STAGES[kind],
    }


def verify_reference(kind, directory):
    details = reference_details(kind)
    root = Path(directory).resolve(strict=True)
    if kind == "RECEIPT":
        path = root.parent / "GECC-20261107-v4-survey-corrected" / details["filename"]
    else:
        path = root / details["filename"]
    if not path.is_file():
        raise ValueError("V2 reference is missing.")
    actual = sha256(path.read_bytes()).hexdigest().upper()
    if actual != details["sha256"]:
        raise ValueError("V2 reference fingerprint mismatch.")
    return details


def project_document_projection_v2(snapshot, kind, project_code, msr_version):
    """Project shared MSR facts only; do not assert later-stage evidence."""
    details = reference_details(kind)
    if not isinstance(project_code, str) or not project_code.strip():
        raise ValueError("Project code is required.")
    if not isinstance(msr_version, str) or not msr_version.strip():
        raise ValueError("Approved MSR version is required.")

    common = customer_document_data(snapshot)
    if not common["customer"].strip():
        raise ValueError("MSR customer name is required.")

    result = {
        "reference": details,
        "project_code": project_code.strip(),
        "msr_version": msr_version.strip(),
        "customer_name": common["customer"],
        "billing_address": common["billing_address"],
        "project_address": common["project_location"],
        "project_city": common["project_city"],
        "project_state": common["project_state"],
        "project_zip": common["project_zip"],
        "customer_phone": common["customer_phone"],
        "customer_email": common["customer_email"],
    }
    if kind in EQUIPMENT_KINDS:
        result["msr_equipment_source"] = deepcopy(common["equipment"])

    # Funding, payments, serial numbers, customer initials, waivers,
    # manager decisions, signing, and completion require separate evidence.
    result["send_authorized"] = False
    result["legally_eligible_for_installation"] = False
    return deepcopy(result)