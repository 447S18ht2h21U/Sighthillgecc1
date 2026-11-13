"""Read-only exact Receipt correlation; never provider authentication."""
import hashlib

from .models import Document, ReceiptDispatchOutbox, ReceiptSendingObservation


def assess_receipt_chain(*, project, documents, outboxes, observations):
    msr = getattr(project, "current_approved", None)
    project_id = getattr(project, "pk", None)
    msr_id = getattr(msr, "pk", None)

    result = {
        "status": "UNVERIFIED",
        "approved_msr_id": str(msr_id) if msr_id else None,
        "valid_pdf_candidates": 0,
        "matching_outbox_intents": 0,
        "matching_local_observations": 0,
        "final_receipt_verified": False,
        "provider_email_authenticated": False,
        "customer_delivery_verified": False,
        "completion_authorized": False,
        "blockers": [],
    }

    if (
        project_id is None
        or msr_id is None
        or getattr(project, "state", None) == "CANCELLED"
        or getattr(msr, "status", None) != "APPROVED"
        or getattr(msr, "project_id", None) != project_id
        or not isinstance(getattr(msr, "snapshot", None), dict)
    ):
        result["blockers"].append(
            "Current approved MSR for an active project is required."
        )
        return result

    email = msr.snapshot.get("customer_email")
    if not isinstance(email, str) or not email.strip():
        result["blockers"].append(
            "Approved customer email address is missing."
        )
        return result

    email = email.strip().casefold()
    candidates = {}

    for doc in documents:
        if (
            getattr(doc, "msr_id", None) != msr_id
            or getattr(doc, "kind", None) != Document.Kind.INVOICE
            or getattr(doc, "status", None) != "PREPARATION"
        ):
            continue
        try:
            content = bytes(doc.content)
        except (TypeError, ValueError, AttributeError):
            continue
        digest = hashlib.sha256(content).hexdigest()
        recorded = getattr(doc, "pdf_sha256", None)
        if (
            len(content) >= 8
            and content.startswith(b"%PDF-")
            and isinstance(recorded, str)
            and digest == recorded.lower()
        ):
            candidates[str(doc.pk)] = digest

    result["valid_pdf_candidates"] = len(candidates)

    for entry in outboxes:
        doc_id = str(getattr(entry, "document_id", ""))
        recipient = getattr(entry, "recipient_email", None)
        if (
            getattr(entry, "project_id", None) == project_id
            and getattr(entry, "msr_id", None) == msr_id
            and getattr(entry, "status", None) == "PENDING"
            and doc_id in candidates
            and isinstance(recipient, str)
            and recipient.strip().casefold() == email
            and getattr(entry, "pdf_sha256", None) == candidates[doc_id]
        ):
            result["matching_outbox_intents"] += 1

    for entry in observations:
        doc_id = str(getattr(entry, "document_id", ""))
        recipient = getattr(entry, "recipient_email", None)
        if (
            getattr(entry, "msr_id", None) == msr_id
            and getattr(entry, "status", None) == "UNVERIFIED"
            and doc_id in candidates
            and isinstance(recipient, str)
            and recipient.strip().casefold() == email
            and getattr(entry, "pdf_sha256", None) == candidates[doc_id]
        ):
            result["matching_local_observations"] += 1

    result["blockers"].extend((
        "Historical Invoice PDFs do not establish final Receipt issuance.",
        "A pending outbox request does not prove email sending.",
        "Local observations do not authenticate email-provider evidence.",
        "Authenticated sending of the exact final Receipt is required.",
    ))
    return result


def inspect_receipt_chain(project):
    """Read only records for the current approved project/MSR."""
    msr = project.current_approved
    if msr is None:
        return assess_receipt_chain(
            project=project, documents=[], outboxes=[], observations=[]
        )

    return assess_receipt_chain(
        project=project,
        documents=Document.objects.filter(
            msr_id=msr.pk, kind=Document.Kind.INVOICE
        ),
        outboxes=ReceiptDispatchOutbox.objects.filter(
            project_id=project.pk, msr_id=msr.pk
        ),
        observations=ReceiptSendingObservation.objects.filter(
            msr_id=msr.pk
        ),
    )
