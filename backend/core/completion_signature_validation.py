"""Pure completed-envelope validation; no provider calls or database writes."""

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError


def verified_timestamp(value):
    """Require an offset-aware provider timestamp that is not in the future."""
    if not isinstance(value, str) or not value or len(value) >= 100:
        raise ValidationError("Invalid provider signing timestamp.")
    try:
        parsed = parse_datetime(value)
    except (TypeError, ValueError, OverflowError):
        parsed = None
    if parsed is None or timezone.is_naive(parsed) or parsed > timezone.now():
        raise ValidationError("Invalid provider signing timestamp.")
    return parsed


def validate_completed_envelope(expected_envelope_id, summary):
    """Validate completion metadata; does not authenticate provider origin."""
    if not isinstance(summary, dict):
        raise ValidationError("Invalid provider envelope metadata.")
    if summary.get("envelopeId") != expected_envelope_id or summary.get("status") != "completed":
        raise ValidationError("Expected completed envelope was not confirmed.")
    completed_at = verified_timestamp(summary.get("completedDateTime"))
    return {"envelope_id": expected_envelope_id, "completed_at": completed_at.isoformat()}


def validate_completed_signers(expected, recipients, completed_at):
    """Validate two completed recipients; does not authenticate provider origin."""
    if not isinstance(expected, dict) or not isinstance(recipients, dict):
        raise ValidationError("Invalid completion signer metadata.")
    recipient_plan = expected.get("recipients")
    if not isinstance(recipient_plan, dict):
        raise ValidationError("Invalid approved recipient metadata.")
    planned = recipient_plan.get("signers")
    actual = recipients.get("signers")
    if not isinstance(planned, list) or len(planned) != 2 or not isinstance(actual, list) or len(actual) != 2:
        raise ValidationError("Exactly two expected completion signers are required.")
    expected_orders = {str(s.get("recipientId")): str(s.get("routingOrder")) for s in planned if isinstance(s, dict)}
    if expected_orders != {"1": "2", "2": "1"}:
        raise ValidationError("Completion certificates require GECC-first routing.")
    finish_time = verified_timestamp(completed_at)
    results = []
    for signer in planned:
        matches = [item for item in actual if isinstance(item, dict) and item.get("recipientId") == signer.get("recipientId")]
        if len(matches) != 1:
            raise ValidationError("Expected completion signer is missing or duplicated.")
        observed = matches[0]
        if any(observed.get(key) != signer.get(key) for key in ("name", "email", "routingOrder")):
            raise ValidationError("Completion signer identity or routing differs.")
        if observed.get("status") != "completed":
            raise ValidationError("Both completion signers must finish signing.")
        signed_at = verified_timestamp(observed.get("signedDateTime"))
        if signed_at > finish_time:
            raise ValidationError("Signer timestamp exceeds envelope completion.")
        results.append({"recipient_id": signer["recipientId"], "signed_at": signed_at.isoformat()})
    signed_times = {item["recipient_id"]: verified_timestamp(item["signed_at"]) for item in results}
    if signed_times["2"] > signed_times["1"]:
        raise ValidationError("Customer signature precedes the required GECC signature.")
    return results


def validate_signature_tabs(expected, recipients):
    """Compare observed signing tabs with approved positions and requirements."""
    if not isinstance(expected, dict) or not isinstance(recipients, dict):
        raise ValidationError("Invalid signature-tab metadata.")
    recipient_plan = expected.get("recipients")
    if not isinstance(recipient_plan, dict):
        raise ValidationError("Invalid approved recipient metadata.")
    planned = recipient_plan.get("signers")
    actual = recipients.get("signers")
    if not isinstance(planned, list) or len(planned) != 2 or not isinstance(actual, list) or len(actual) != 2:
        raise ValidationError("Invalid completion signer list.")
    keys = ("documentId", "pageNumber", "xPosition", "yPosition", "tabLabel")
    for signer in planned:
        if not isinstance(signer, dict) or not isinstance(signer.get("tabs"), dict):
            raise ValidationError("Approved signing tabs are missing.")
        matches = [item for item in actual if isinstance(item, dict) and item.get("recipientId") == signer.get("recipientId")]
        if len(matches) != 1 or not isinstance(matches[0].get("tabs"), dict):
            raise ValidationError("Provider signing tabs are missing.")
        observed_tabs = matches[0]["tabs"]
        planned_tabs = signer["tabs"]
        for tab_type, entries in planned_tabs.items():
            seen = observed_tabs.get(tab_type)
            if not isinstance(entries, list) or not isinstance(seen, list) or len(entries) != len(seen):
                raise ValidationError("Signing-tab count changed.")
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValidationError("Invalid approved signing tab.")
                found = [tab for tab in seen if isinstance(tab, dict) and all(str(tab.get(key, "")) == str(entry.get(key, "")) for key in keys)]
                if len(found) != 1:
                    raise ValidationError("Required signing-tab placement changed.")
                if entry.get("optional") == "false" and str(found[0].get("optional", "")).lower() != "false":
                    raise ValidationError("Required signing tab became optional.")
        for tab_type, entries in observed_tabs.items():
            if tab_type not in planned_tabs and isinstance(entries, list) and entries:
                raise ValidationError("Unexpected signing tabs detected.")
    return True


def validate_completion_documents(expected, documents):
    """Validate provider document identity, not signed PDF authenticity."""
    if not isinstance(expected, dict) or not isinstance(documents, dict):
        raise ValidationError("Invalid completion document metadata.")
    planned = expected.get("documents")
    observed = documents.get("envelopeDocuments")
    if not isinstance(planned, list) or not planned or not isinstance(observed, list):
        raise ValidationError("Completion document list is missing.")
    def identity(entry):
        if not isinstance(entry, dict):
            raise ValidationError("Invalid completion document entry.")
        document_id = entry.get("documentId")
        name = entry.get("name")
        if not isinstance(document_id, str) or not document_id or not isinstance(name, str) or not name:
            raise ValidationError("Invalid completion document identity.")
        return document_id, name
    expected_pairs = [identity(entry) for entry in planned]
    if len({item[0] for item in expected_pairs}) != len(expected_pairs):
        raise ValidationError("Duplicate approved document identifier.")
    regular = []
    certificates = []
    for entry in observed:
        if not isinstance(entry, dict):
            raise ValidationError("Invalid provider document entry.")
        if entry.get("documentId") == "certificate":
            certificates.append(entry)
        else:
            regular.append(identity(entry))
    if len(certificates) > 1:
        raise ValidationError("Duplicate provider completion certificate.")
    if len(regular) != len(expected_pairs) or set(regular) != set(expected_pairs):
        raise ValidationError("Completed-envelope document identities changed.")
    return [{"document_id": item[0], "name": item[1]} for item in expected_pairs]


def validate_signed_pdf_bundle(expected_document_ids, pdf_documents):
    """Validate supplied PDF bytes and return hashes; no provider or database access."""
    import hashlib
    from io import BytesIO
    from pypdf import PdfReader

    max_pdf_bytes = 8 * 1024 * 1024
    max_bundle_bytes = 24 * 1024 * 1024
    if not isinstance(expected_document_ids, (list, tuple)) or not expected_document_ids:
        raise ValidationError("Expected signed-document identifiers are missing.")
    if any(not isinstance(item, str) or not item or item == "certificate" for item in expected_document_ids):
        raise ValidationError("Invalid expected signed-document identifier.")
    expected = set(expected_document_ids) | {"certificate"}
    if len(expected_document_ids) != len(set(expected_document_ids)):
        raise ValidationError("Duplicate expected signed-document identifier.")
    if not isinstance(pdf_documents, dict) or set(pdf_documents) != expected:
        raise ValidationError("Signed-document bundle is incomplete or contains unexpected documents.")
    result = []
    total = 0
    for document_id in [*expected_document_ids, "certificate"]:
        content = pdf_documents[document_id]
        if not isinstance(content, bytes) or not content.startswith(b"%PDF-"):
            raise ValidationError("Invalid signed PDF content.")
        size = len(content)
        total += size
        if size > max_pdf_bytes or total > max_bundle_bytes:
            raise ValidationError("Signed-document bundle exceeds the allowed size.")
        try:
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted or not 1 <= len(reader.pages) <= 150:
                raise ValueError("Invalid PDF page structure.")
        except Exception:
            raise ValidationError("Signed-document PDF validation failed.") from None
        result.append({"document_id": document_id, "pdf_sha256": hashlib.sha256(content).hexdigest(), "size_bytes": size})
    return result
