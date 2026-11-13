"""Default-disabled, POST-only sender OAuth initiation endpoint."""
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .completion_send_oauth_4627 import begin as begin_sender
from .docusign_api import private


@api_view(["POST"])
def connect(request, attempt_id):
    result = begin_sender(
        actor=request.user,
        attempt_id=attempt_id,
        session_key=request.session.session_key,
    )
    return private(Response(result))
