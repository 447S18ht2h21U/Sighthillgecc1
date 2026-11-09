"""Approved three-stage Invoice workflow: unregistered policy foundation.

This module does not grant installation authority, interpret cancellation
law, change live signatures, send documents, or verify provider delivery.
"""
from dataclasses import dataclass
from enum import Enum


class InvoiceStage(str, Enum):
    PRE_INSTALLATION = "PRE_INSTALLATION"
    EQUIPMENT_IDENTIFICATION = "EQUIPMENT_IDENTIFICATION"
    POST_INSTALLATION_DELIVERY = "POST_INSTALLATION_DELIVERY"


@dataclass(frozen=True)
class WorkflowAssessment:
    stage: InvoiceStage
    requirements_satisfied: bool
    outstanding: tuple[str, ...]
    installation_authorized: bool = False
    delivery_verified: bool = False


def _require_flags(flags, required):
    if not isinstance(flags, dict) or set(flags) != set(required):
        raise ValueError("Exactly the required workflow flags must be supplied.")
    if any(type(value) is not bool for value in flags.values()):
        raise ValueError("Workflow flags must be explicit booleans.")


def assess_pre_installation(
    *,
    approved_msr,
    contract_signed,
    cancellation_cleared,
    waiting_period_cleared,
    payment_cleared,
):
    """Invoice signature and post-installation delivery are NOT prerequisites.

    The supplied clearance flags must ultimately be established by
    independently verified operational services; not by user claims.
    """
    flags = {
        "approved_msr": approved_msr,
        "contract_signed": contract_signed,
        "cancellation_cleared": cancellation_cleared,
        "waiting_period_cleared": waiting_period_cleared,
        "payment_cleared": payment_cleared,
    }
    _require_flags(flags, flags.keys())
    outstanding = tuple(key for key, value in flags.items() if not value)
    return WorkflowAssessment(
        InvoiceStage.PRE_INSTALLATION,
        not outstanding,
        outstanding,
    )


def assess_equipment_identification(
    *,
    physical_units_accounted_for,
    serials_recorded_or_exceptions_approved,
):
    flags = {
        "physical_units_accounted_for": physical_units_accounted_for,
        "serials_recorded_or_exceptions_approved":
            serials_recorded_or_exceptions_approved,
    }
    _require_flags(flags, flags.keys())
    outstanding = tuple(key for key, value in flags.items() if not value)
    return WorkflowAssessment(
        InvoiceStage.EQUIPMENT_IDENTIFICATION,
        not outstanding,
        outstanding,
    )


def assess_post_installation_delivery(
    *,
    installation_completed,
    final_invoice_prepared,
    versioned_addendum_prepared,
    independently_verified_delivery,
):
    flags = {
        "installation_completed": installation_completed,
        "final_invoice_prepared": final_invoice_prepared,
        "versioned_addendum_prepared": versioned_addendum_prepared,
        "independently_verified_delivery": independently_verified_delivery,
    }
    _require_flags(flags, flags.keys())
    outstanding = tuple(key for key, value in flags.items() if not value)
    # This foundation cannot itself authenticate external delivery.
    # Even matching supplied flags never produce a trusted delivery result.
    return WorkflowAssessment(
        InvoiceStage.POST_INSTALLATION_DELIVERY,
        not outstanding,
        outstanding,
    )