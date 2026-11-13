"""Audited recording of pending customer payments."""
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import CustomerPayment, Project, Role, User
from .operational_visibility import operational_project_scope
from .rules import EASTERN
from .services import audit


def require_payment_comptroller(actor):
    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None) != Role.COMPTROLLER
        or not User.objects.filter(
            pk=actor.pk, is_active=True, role=Role.COMPTROLLER
        ).exists()
    ):
        raise PermissionDenied(
            "An active Comptroller is required for customer payment operations."
        )
    return actor


@transaction.atomic
def record_pending_customer_payment(
    *, actor, project_id, kind, amount, received_date, payment_reference
):
    require_payment_comptroller(actor)

    project = Project.objects.select_for_update().filter(
        pk=project_id
    ).first()

    if (
        project is None
        or not operational_project_scope(actor).filter(
            pk=project.pk
        ).exists()
    ):
        raise PermissionDenied(
            "Project is outside authorized operational scope."
        )

    if project.state == "CANCELLED" or project.current_approved_id is None:
        raise ValidationError(
            "An active project with a current approved MSR is required."
        )

    msr = project.current_approved

    if msr.status != "APPROVED" or msr.project_id != project.pk:
        raise ValidationError("Current approved MSR is invalid.")

    if kind not in CustomerPayment.Kind.values:
        raise ValidationError("Invalid customer payment type.")

    if (
        not isinstance(amount, Decimal)
        or not amount.is_finite()
        or amount <= 0
    ):
        raise ValidationError("Payment amount must be positive.")

    if type(received_date) is not date:
        raise ValidationError("A valid received date is required.")

    if received_date > timezone.now().astimezone(EASTERN).date():
        raise ValidationError("Future received dates are not permitted.")

    if not isinstance(payment_reference, str):
        raise ValidationError("Payment reference must be text.")

    reference = payment_reference.strip()

    if not reference:
        raise ValidationError("Payment reference is required.")

    if CustomerPayment.objects.filter(
        project=project,
        payment_reference=reference,
    ).exists():
        raise ValidationError(
            "Payment reference already exists for this project."
        )

    payment = CustomerPayment.objects.create(
        project=project,
        msr=msr,
        kind=kind,
        amount=amount,
        received_date=received_date,
        payment_reference=reference,
        status=CustomerPayment.Status.PENDING,
        recorded_by=actor,
    )

    audit(actor, "customer.payment.recorded", payment.pk, {
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "kind": kind,
        "amount": str(amount),
        "received_date": received_date.isoformat(),
        "payment_reference": reference,
        "status": "PENDING",
        "bank_confirmed": False,
    })

    return payment
