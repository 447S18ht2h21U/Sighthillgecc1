"""Receipt email transport foundation: test backend only.

A successful send is NOT provider-authenticated customer delivery proof.
No production or network email backend is allowed by this service.
"""
import hashlib
import re
from dataclasses import dataclass

from django.core.mail import EmailMessage, get_connection
from django.core.mail.backends.locmem import EmailBackend
from django.core.exceptions import ValidationError


@dataclass(frozen=True)
class ReceiptTransportResult:
    recipient: str
    pdf_sha256: str
    submitted_to_test_backend: bool
    provider_authenticated: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def send_receipt_to_test_backend(
    *, pdf_bytes, expected_sha256, recipient, approved_email,
    from_email="care@gecc.cloud", connection=None,
):
    """Send ONLY to an explicitly supplied in-memory test connection."""
    if connection is None or type(connection) is not EmailBackend:
        raise ValidationError("Only the in-memory test backend is permitted.")
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF-"):
        raise ValidationError("Retained PDF bytes required.")
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    if (
        not isinstance(expected_sha256, str)
        or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256)
        or digest != expected_sha256.lower()
    ):
        raise ValidationError("Retained PDF fingerprint mismatch.")
    if (
        not isinstance(recipient, str)
        or not isinstance(approved_email, str)
        or not recipient.strip()
        or recipient.strip().casefold() != approved_email.strip().casefold()
        or "\n" in recipient
        or "\r" in recipient
    ):
        raise ValidationError("Recipient does not match approved MSR.")
    if from_email != "care@gecc.cloud":
        raise ValidationError("Unexpected sender identity.")

    message = EmailMessage(
        subject="Green Energy Contracting Corporation - Receipt",
        body="Attached is your project Receipt.",
        from_email=from_email,
        to=[recipient.strip()],
        connection=connection,
    )
    message.attach("Receipt.pdf", pdf_bytes, "application/pdf")
    if message.send(fail_silently=False) != 1:
        raise ValidationError("Test transport did not accept message.")
    return ReceiptTransportResult(
        recipient=recipient.strip(),
        pdf_sha256=digest,
        submitted_to_test_backend=True,
    )