"""Read-only completion-envelope inspection API; no provider operations."""

from django.http import Http404
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import CompletionEnvelopeAttempt
from .completion_envelope_inspection import inspect_attempt
from .docusign_api import private


def secure_responses(view):
    def wrapped(request, *args, **kwargs):
        return private(view(request, *args, **kwargs))
    return wrapped


@secure_responses
@api_view(["GET"])
def detail(request, attempt_id):
    """Inspect an existing local attempt without verifying provider evidence."""
    try:
        result = inspect_attempt(request.user, attempt_id)
    except CompletionEnvelopeAttempt.DoesNotExist:
        raise Http404("Completion-envelope attempt not found.") from None

    return private(Response(result))
