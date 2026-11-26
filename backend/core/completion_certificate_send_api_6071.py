"""Authenticated fictional certificate transmission API."""

from rest_framework.decorators import (
    api_view,
    permission_classes,
    parser_classes,
)

from rest_framework.permissions import IsAuthenticated

from rest_framework.parsers import JSONParser

from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from .docusign_api import private

from rest_framework.response import Response

from .distributor_invoice_api_6006 import _reader

from .completion_certificate_send_6071 import (
    PROJECT_ID,
    begin,
    status,
)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def certificate_send(request, project_id):

    if str(project_id) != PROJECT_ID:

        raise PermissionDenied(
            "Designated fictional project required."
        )

    actor = _reader(request)

    if request.method == "GET":

        return private(
            Response(status(actor))
        )

    if (
        type(request.data) is not dict
        or set(request.data) != {
            "envelope_id",
            "recipient",
            "confirmed",
        }
    ):

        raise ValidationError(
            "Exact sandbox transmission confirmation required."
        )

    return private(Response(begin(
        actor=actor,
        session_key=request.session.session_key,
        project_id=project_id,
        **request.data,
    )))
