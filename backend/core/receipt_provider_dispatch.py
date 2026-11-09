"""Provider dispatch boundary; intentionally disabled for live sending.

Transport acceptance does not prove customer delivery. No database
records, completion authorization, or provider credentials are handled.
"""
import hashlib
import re
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail.backends.locmem import EmailBackend as MemoryBackend

from .receipt_email_transport import send_receipt_to_test_backend


@dataclass(frozen=True)
class ReceiptDispatchDecision:
    pdf_sha256: str
    recipient: str
    test_submission: bool
    provider_authenticated: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def dispatch_receipt(
    *,
    pdf_bytes,
    expected_sha256,
    recipient,
    approved_email,
    connection=None,
    mode="DISABLED",
):
    """Accept only explicit in-memory test dispatch.

    Production path remains closed pending approved provider integration
    and independent provider-authenticated send verification.
    """
    if mode != "TEST_MEMORY":
        raise ValidationError(
            "Live Receipt email dispatch has not been authorized."
        )

    if connection is None or type(connection) is not MemoryBackend:
        raise ValidationError("Explicit in-memory test backend required.")

    if not isinstance(recipient, str) or not isinstance(approved_email, str):
        raise ValidationError("Approved customer email required.")
    if not re.fullmatch(
        r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+",
        recipient.strip(),
    ):
        raise ValidationError("Invalid recipient email.")
    if recipient.strip().casefold() != approved_email.strip().casefold():
        raise ValidationError("Recipient differs from approved MSR.")

    if not isinstance(pdf_bytes, bytes):
        raise ValidationError("Receipt PDF bytes required.")
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    if (
        not isinstance(expected_sha256, str)
        or digest != expected_sha256.lower()
    ):
        raise ValidationError("Receipt PDF fingerprint mismatch.")

    result = send_receipt_to_test_backend(
        pdf_bytes=pdf_bytes,
        expected_sha256=expected_sha256,
        recipient=recipient,
        approved_email=approved_email,
        connection=connection,
    )
    return ReceiptDispatchDecision(
        pdf_sha256=result.pdf_sha256,
        recipient=result.recipient,
        test_submission=result.submitted_to_test_backend,
    )