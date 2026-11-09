"""Unregistered receipt-outbox request API prototype.

No operational URL, provider sending, or completion authorization.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ObjectDoesNotExist
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Document, Project, Role, User
from .receipt_outbox_request_service import request_receipt_outbox


class ReceiptOutboxRequestInput(serializers.Serializer):
    project_id = serializers.CharField(max_length=128)
    document_id = serializers.CharField(max_length=128)
    idempotency_key = serializers.RegexField(
        regex=r"^[A-Za-z0-9_-]{8,128}$",
        max_length=128,
    )


class ReceiptOutboxRequestPrototype(APIView):
    """Restricted prototype: creates PENDING intent, never sends email."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        actor = User.objects.filter(
            pk=request.user.pk,
            is_active=True,
            role=Role.COMPTROLLER,
        ).first()

        if actor is None:
            raise PermissionDenied("Active Comptroller required.")

        if not isinstance(request.data, dict):
            raise serializers.ValidationError("JSON object required.")

        allowed = {"project_id", "document_id", "idempotency_key"}
        if set(request.data) != allowed:
            raise serializers.ValidationError(
                "Only project_id, document_id, and idempotency_key are allowed."
            )

        incoming = ReceiptOutboxRequestInput(data=request.data)
        incoming.is_valid(raise_exception=True)
        data = incoming.validated_data

        try:
            project_pk = Project._meta.pk.to_python(data["project_id"])
            document_pk = Document._meta.pk.to_python(data["document_id"])
        except (TypeError, ValueError, DjangoValidationError):
            raise serializers.ValidationError("Invalid record identifier.")

        try:
            project = Project.objects.select_related(
                "current_approved"
            ).get(pk=project_pk)
            document = Document.objects.get(pk=document_pk)
        except ObjectDoesNotExist:
            raise NotFound("Receipt source record not found.")

        msr = project.current_approved
        if msr is None or not isinstance(msr.snapshot, dict):
            raise serializers.ValidationError(
                "Current approved MSR is required."
            )

        recipient = msr.snapshot.get("customer_email")
        if not isinstance(recipient, str) or not recipient.strip():
            raise serializers.ValidationError(
                "Approved customer email is required."
            )

        try:
            entry = request_receipt_outbox(
                actor=actor,
                project_id=project.pk,
                document_id=document.pk,
                recipient=recipient,
                pdf_bytes=bytes(document.content),
                idempotency_key=data["idempotency_key"],
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        except ObjectDoesNotExist:
            raise NotFound("Receipt source record not found.")

        return Response(
            {
                "outbox_id": str(entry.pk),
                "status": "PENDING",
                "email_sent": False,
                "provider_authenticated": False,
                "delivery_verified": False,
                "completion_authorized": False,
            },
            status=status.HTTP_202_ACCEPTED,
        )