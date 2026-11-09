"""Unregistered DRF endpoint prototype for delegation security testing.

No URL registration. No service dispatch or live authorization activation.
"""

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError

from .msr_delegation_api_boundary import (
    prepare_delegation_command,
    execute_prepared_delegation_command,
)
from .msr_delegation_api_contract import DelegationInputError


class MSRDelegationHTTPPrototype(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ["post", "options"]

    def post(self, request, *args, **kwargs):
        action = kwargs.get("action")

        try:
            command = prepare_delegation_command(
                request, action=action
            )
        except DelegationInputError:
            raise ValidationError({
                "detail": "Invalid delegation request fields."
            }) from None

        # The dispatcher is deliberately fail-closed and always denies.
        return execute_prepared_delegation_command(command)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(
            request, response, *args, **kwargs
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


def prototype_grants_live_msr_access(*args, **kwargs):
    return False