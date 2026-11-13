"""Authenticated, read-only DocuSign completion OAuth initiation."""
from django.db import connections, router
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .completion_provider_oauth_4611 import begin
from .docusign_api import private
from .models import CompletionEnvelopeAttempt


@api_view(["POST"])
def connect(request, attempt_id):
    # A pending operational migration is not a reason to modify the
    # development database or to bypass access checks.
    from .completion_provider_oauth_4611 import _active_comptroller
    _active_comptroller(request.user)

    alias = router.db_for_read(CompletionEnvelopeAttempt)
    connection = connections[alias]

    with connection.cursor() as cursor:
        available = set(connection.introspection.table_names(cursor))

    if CompletionEnvelopeAttempt._meta.db_table not in available:
        raise ValidationError(
            "Completion envelope storage is unavailable pending "
            "controlled migration."
        )

    if not isinstance(request.data, dict) or (
        request.data.get("sandbox_read_confirmed") is not True
    ):
        raise ValidationError(
            "Explicit sandbox completion-read confirmation is required."
        )

    return private(Response(begin(
        request.user,
        request.session.session_key,
        str(attempt_id),
    )))
