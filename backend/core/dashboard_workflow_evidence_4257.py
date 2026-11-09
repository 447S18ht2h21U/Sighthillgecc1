"""Read-only dashboard evidence projection.

This service reports the results of existing prerequisite checks.
It does not grant installation, signing, payment, or completion authority.
The caller must enforce project visibility before invoking it.
"""

from .installation_readiness import installation_readiness


def describe_workflow_evidence(project):
    if project is None or getattr(project, "pk", None) is None:
        raise ValueError("A scoped project record is required.")

    current = getattr(project, "current_approved", None)
    approved = (
        current is not None
        and current.status == "APPROVED"
        and current.project_id == project.pk
        and project.state != "CANCELLED"
    )

    statuses = {
        "approved_msr": "VERIFIED" if approved else "BLOCKED",
        "contract_signature": "NOT_EVALUATED",
        "cancellation_deadline": "NOT_EVALUATED",
        "waiting_period": "NOT_EVALUATED",
        "payment_readiness": "NOT_EVALUATED",
        "installation_authorization": "NOT_EVALUATED",
        "final_invoice_delivery": "NOT_EVALUATED",
        "receipt_delivery": "NOT_EVALUATED",
        "completed_docusign": "NOT_EVALUATED",
        "project_completion": "BLOCKED",
    }

    if approved:
        try:
            report = installation_readiness(project)
            requirements = report["requirements"]

            mapping = {
                "contract_signed": "contract_signature",
                "cancellation_complete": "cancellation_deadline",
                "waiting_period_complete": "waiting_period",
                "deposit_verified": "payment_readiness",
            }

            for source, target in mapping.items():
                value = requirements.get(source)
                if type(value) is bool:
                    # These are prerequisite-check results, not separate
                    # approval, delivery, or installation authority.
                    statuses[target] = (
                        "CHECK_PASSED" if value else "BLOCKED"
                    )
        except Exception:
            # A dashboard error must never become an assumed approval.
            # The underlying operational service remains authoritative.
            pass

    return {
        "read_only": True,
        "evidence_source": "EXISTING_PREREQUISITE_CHECKS",
        "installation_authorized": False,
        "project_completion_authorized": False,
        "statuses": statuses,
    }