"""Unregistered, read-only binding to the current approved project MSR."""
from copy import deepcopy
from uuid import UUID
from rest_framework.exceptions import ValidationError
from .models import Project
from .approved_document_msr_binding_4240 import BindingDenied, inspect_approved_msr_binding
from .tax_entry_authorization_4437I import require_tax_entry_action
from .tax_draft_validation_4437Q import validate_tax_draft

def bind_project_tax_draft(actor, entry):
    require_tax_entry_action(actor, "PREPARE_DRAFT")
    if type(entry) is not dict:
        raise ValidationError("Structured tax draft required.")
    if entry.get("project_related") is not True:
        raise ValidationError("Project-related tax draft required.")
    try:
        project_id = UUID(str(entry.get("project_id")))
        msr_id = UUID(str(entry.get("approved_msr_id")))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValidationError("Valid project and MSR identifiers required.") from error
    project = Project.objects.select_related("current_approved").filter(pk=project_id).first()
    if project is None or project.current_approved_id is None:
        raise ValidationError("Project has no current approved MSR.")
    msr = project.current_approved
    if msr.pk != msr_id or msr.project_id != project.pk or msr.status != "APPROVED":
        raise ValidationError("MSR does not match the approved project version.")
    if type(entry.get("approved_msr_version")) is not int or entry["approved_msr_version"] != msr.number:
        raise ValidationError("Incorrect approved MSR version.")
    try:
        binding = inspect_approved_msr_binding(project, msr)
    except BindingDenied as error:
        raise ValidationError(str(error)) from error
    snapshot = msr.snapshot
    if type(snapshot) is not dict:
        raise ValidationError("Approved MSR snapshot missing.")
    billing = snapshot.get("billing_address")
    installation = snapshot.get("project_location")
    if any(type(value) is not str or not value.strip() for value in (billing, installation)):
        raise ValidationError("Approved MSR address evidence incomplete.")
    for field, trusted in (("billing_address", billing), ("installation_address", installation)):
        supplied = entry.get(field)
        if supplied not in (None, trusted):
            raise ValidationError("Tax address differs from approved MSR.")
    result = deepcopy(entry)
    result["project_id"] = str(project.pk)
    result["approved_msr_id"] = str(msr.pk)
    result["approved_msr_version"] = msr.number
    result["billing_address"] = billing
    result["installation_address"] = installation
    validated = validate_tax_draft(actor, result)
    validated["msr_evidence_source"] = "CURRENT_APPROVED_MSR_SNAPSHOT"
    validated["msr_snapshot_sha256"] = binding.snapshot_sha256
    validated["eligible_for_financial_reporting"] = False
    return validated
