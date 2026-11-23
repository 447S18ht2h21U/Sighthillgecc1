"""Fail-closed commercial customer signature trust boundary.

Pure classification only. This module cannot authenticate DocuSign,
create evidence, or authorize installation. No untrusted caller-supplied
metadata may promote a signature to VERIFIED.
"""

from rest_framework.exceptions import ValidationError


def require_authenticated_commercial_signature(*, evidence):
    """Reject legacy, synthetic, and unbound signature assertions.

    Future integration must obtain durable authenticated provider proof
    through an independently controlled verifier. Do not replace this
    gate with a provider-reference string or a caller-supplied flag.
    """
    if evidence is None:
        raise ValidationError(
            "Authenticated DocuSign customer signature evidence is required."
        )

    raise ValidationError(
        "Commercial signature authentication is not operationally "
        "connected. A stored signature record alone cannot authorize "
        "installation."
    )
