"""Read-only envelope binding consistency checks; not provider authentication."""

from uuid import UUID
from rest_framework.exceptions import ValidationError
from .documents import canonical_hash


def validate_envelope_binding(package, binding):
    """Validate a recorded association; does not establish its provenance."""
    if package is None or not isinstance(binding, dict):
        raise ValidationError("Completion envelope binding is missing.")
    if package.plan.group not in ("COMPLETION_FINANCED", "COMPLETION_NON_FINANCED"):
        raise ValidationError("Envelope binding requires a completion signing plan.")
    keys = ("release_package_id", "release_package_digest", "signing_plan_id", "signing_plan_digest", "provider_account_id", "provider_envelope_id")
    if any(not isinstance(binding.get(key), str) or not binding[key] for key in keys):
        raise ValidationError("Envelope binding identifiers are incomplete.")
    try:
        account = str(UUID(binding["provider_account_id"]))
        envelope = str(UUID(binding["provider_envelope_id"]))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid provider account or envelope identifier.") from None
    if account != binding["provider_account_id"] or envelope != binding["provider_envelope_id"]:
        raise ValidationError("Provider identifiers must use canonical UUID form.")
    if (binding["release_package_id"] != str(package.pk)
            or binding["release_package_digest"] != package.digest
            or binding["signing_plan_id"] != str(package.plan_id)
            or binding["signing_plan_digest"] != package.plan.digest):
        raise ValidationError("Envelope binding does not match the approved release.")
    recorded_digest = binding.get("binding_digest")
    content = {key: binding[key] for key in keys}
    if not isinstance(recorded_digest, str) or recorded_digest != canonical_hash(content):
        raise ValidationError("Envelope binding digest verification failed.")
    return {"release_package_id": str(package.pk), "provider_account_id": account, "provider_envelope_id": envelope, "binding_digest": recorded_digest, "provider_authenticated": False}
