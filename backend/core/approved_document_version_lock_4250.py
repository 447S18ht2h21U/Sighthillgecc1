"""Read-only approved MSR and six-PDF review binding.

This is a development-only integrity verifier, not a release gate,
API endpoint, signature approval, or substitute for authorization.
"""
from .approved_document_msr_binding_4240 import (
    BindingDenied,
    inspect_approved_msr_binding,
)
from .approved_document_lifecycle_4248 import LifecycleDenied
from .approved_document_lifecycle_integration_4249 import (
    inspect_integrated_document_lifecycle,
)


def inspect_version_locked_review(*, project, msr, batch):
    """Require current approved MSR and exact review provenance."""
    if type(batch) is not dict:
        raise LifecycleDenied("A complete review batch is required.")

    try:
        binding = inspect_approved_msr_binding(project, msr)
    except BindingDenied as exc:
        raise LifecycleDenied(
            "Current approved MSR binding failed."
        ) from exc

    record = batch.get("record")
    if record is None:
        raise LifecycleDenied("Review record is missing.")

    expected = (
        ("project_id", binding.project_id),
        ("msr_id", binding.msr_id),
        ("version", binding.version),
        ("snapshot_sha256", binding.snapshot_sha256),
        ("financing_type", msr.snapshot["financing_type"]),
    )

    for field, value in expected:
        if type(getattr(record, field, None)) is not type(value):
            raise LifecycleDenied(
                "Document review identity or snapshot type mismatch."
            )
        if getattr(record, field) != value:
            raise LifecycleDenied(
                "Document review does not match the current approved MSR."
            )

    return inspect_integrated_document_lifecycle(batch)