"""Comptroller-controlled customer payment workflow API."""
from django.db import transaction
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .customer_payment_recording_4714 import (
    record_pending_customer_payment,
    require_payment_comptroller,
)
from .customer_payment_bank_confirmation_services import (
    confirm_customer_payment_bank_availability,
)
from .payment_services import verify_customer_payment
from .models import CustomerPayment
from .operational_visibility import operational_project_scope


class RecordPaymentInput(serializers.Serializer):
    project = serializers.UUIDField()
    kind = serializers.ChoiceField(
        choices=CustomerPayment.Kind.choices
    )
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2
    )
    received_date = serializers.DateField()
    payment_reference = serializers.CharField(
        max_length=150, allow_blank=False, trim_whitespace=True
    )


class BankConfirmationInput(serializers.Serializer):
    bank_reference = serializers.CharField(max_length=150)
    confirmation_date = serializers.DateField()
    confirmation_method = serializers.CharField(max_length=100)
    confirmation_note = serializers.CharField(max_length=2000)


def payment_details(payment):
    confirmation = getattr(payment, "bank_confirmation", None)

    return {
        "id": str(payment.pk),
        "project": str(payment.project_id),
        "msr": str(payment.msr_id),
        "kind": payment.kind,
        "amount": str(payment.amount),
        "received_date": payment.received_date.isoformat(),
        "payment_reference": payment.payment_reference,
        "status": payment.status,
        "bank_confirmed": confirmation is not None,
        "confirmation_date": (
            confirmation.confirmation_date.isoformat()
            if confirmation is not None else None
        ),
    }


class CustomerPaymentViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]
    queryset = CustomerPayment.objects.none()

    def get_queryset(self):
        require_payment_comptroller(self.request.user)
        return (
            CustomerPayment.objects
            .filter(
                project__in=operational_project_scope(
                    self.request.user
                )
            )
            .select_related("bank_confirmation")
            .order_by("-created_at", "-pk")
        )

    def list(self, request):
        rows = self.get_queryset()
        project_id = request.query_params.get("project")

        if project_id:
            project_id = serializers.UUIDField().run_validation(
                project_id
            )
            rows = rows.filter(project_id=project_id)

        return Response([
            payment_details(payment)
            for payment in rows[:250]
        ])

    def create(self, request):
        require_payment_comptroller(request.user)
        fields = RecordPaymentInput(data=request.data)
        fields.is_valid(raise_exception=True)

        payment = record_pending_customer_payment(
            actor=request.user,
            project_id=fields.validated_data["project"],
            kind=fields.validated_data["kind"],
            amount=fields.validated_data["amount"],
            received_date=fields.validated_data["received_date"],
            payment_reference=fields.validated_data["payment_reference"],
        )

        return Response(
            payment_details(payment),
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        require_payment_comptroller(request.user)

        with transaction.atomic():
            payment = self.get_object()
            result = verify_customer_payment(
                request.user, payment.pk
            )

        return Response(payment_details(result))

    @action(
        detail=True,
        methods=["post"],
        url_path="bank-confirm",
    )
    def bank_confirm(self, request, pk=None):
        require_payment_comptroller(request.user)
        fields = BankConfirmationInput(data=request.data)
        fields.is_valid(raise_exception=True)

        with transaction.atomic():
            payment = self.get_object()
            confirm_customer_payment_bank_availability(
                actor=request.user,
                payment_id=payment.pk,
                **fields.validated_data,
            )

        payment.refresh_from_db()
        return Response(payment_details(payment))
