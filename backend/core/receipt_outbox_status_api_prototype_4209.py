"""Unregistered read-only receipt outbox status API.

PENDING means a durable request exists. It is not proof of sending,
provider authentication, customer delivery, or project completion.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ReceiptDispatchOutbox, Role, User


class ReceiptOutboxStatusPrototype(APIView):
    """Comptroller-only status inspection; no email or record mutations."""

    permission_classes = [IsAuthenticated]

    def get(self, request, outbox_id):
        actor_pk = getattr(request.user, "pk", None)
        if actor_pk is None:
            raise PermissionDenied("Active Comptroller required.")

        authorized = User.objects.filter(
            pk=actor_pk,
            is_active=True,
            role=Role.COMPTROLLER,
        ).exists()

        if not authorized:
            raise PermissionDenied("Active Comptroller required.")

        try:
            identifier = ReceiptDispatchOutbox._meta.pk.to_python(
                outbox_id
            )
        except (TypeError, ValueError, DjangoValidationError):
            raise NotFound("Receipt outbox record not found.")

        entry = ReceiptDispatchOutbox.objects.filter(
            pk=identifier
        ).first()

        if entry is None:
            raise NotFound("Receipt outbox record not found.")

        if entry.status != "PENDING":
            raise PermissionDenied(
                "Unexpected receipt outbox state; manual review required."
            )

        return Response({
            "outbox_id": str(entry.pk),
            "project_id": str(entry.project_id),
            "document_id": str(entry.document_id),
            "status": "PENDING",
            "email_sent": False,
            "provider_authenticated": False,
            "delivery_verified": False,
            "completion_authorized": False,
        })