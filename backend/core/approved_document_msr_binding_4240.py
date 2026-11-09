"""Read-only approved-MSR identity preflight.

Not an authorization decision, document-generation service, API route,
payment check, or approval record. The operational services remain authoritative.
"""
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json


class BindingDenied(ValueError):
    """Project/MSR binding cannot be trusted for document review."""


@dataclass(frozen=True)
class ApprovedMSRBinding:
    project_id: str
    msr_id: str
    version: int
    snapshot_sha256: str
    review_only: bool = True


def inspect_approved_msr_binding(project, msr):
    """Inspect an already-loaded project and MSR without database writes."""
    if project is None or msr is None:
        raise BindingDenied("Project and MSR are required.")

    project_id = str(getattr(project, "pk", None) or "")
    msr_id = str(getattr(msr, "pk", None) or "")

    if not project_id or project_id == "None":
        raise BindingDenied("Project identity is missing.")
    if not msr_id or msr_id == "None":
        raise BindingDenied("MSR identity is missing.")

    if str(getattr(msr, "project_id", "")) != project_id:
        raise BindingDenied("MSR belongs to a different project.")

    if str(getattr(project, "current_approved_id", "")) != msr_id:
        raise BindingDenied("MSR is not the current approved version.")

    if getattr(msr, "status", None) != "APPROVED":
        raise BindingDenied("MSR must be approved.")

    if getattr(project, "state", None) == "CANCELLED":
        raise BindingDenied("Cancelled projects are not eligible.")

    version = getattr(msr, "number", None)
    if type(version) is not int or version < 1:
        raise BindingDenied("Invalid MSR version.")

    snapshot = getattr(msr, "snapshot", None)
    if type(snapshot) is not dict:
        raise BindingDenied("Approved MSR snapshot is missing.")

    snapshot = deepcopy(snapshot)

    if not isinstance(snapshot.get("customer"), str):
        raise BindingDenied("MSR customer name is missing.")
    if not snapshot["customer"].strip():
        raise BindingDenied("MSR customer name is empty.")

    if snapshot.get("financing_type") not in (
        "FINANCED", "NON_FINANCED"
    ):
        raise BindingDenied("Invalid financing classification.")

    try:
        canonical = json.dumps(
            snapshot, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise BindingDenied("MSR snapshot cannot be fingerprinted.") from exc

    return ApprovedMSRBinding(
        project_id=project_id,
        msr_id=msr_id,
        version=version,
        snapshot_sha256=sha256(canonical).hexdigest().upper(),
    )