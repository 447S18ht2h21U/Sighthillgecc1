"""Server-selected request metadata; never copy credentials or query values."""
from contextvars import ContextVar
from uuid import UUID, uuid4

request_context = ContextVar('audit_request_context', default=None)
NO_RESOURCE = UUID(int=0)


def context_for(request):
    match = request.resolver_match
    return {
        'source': 'HTTP', 'request_id': str(uuid4()),
        'method': request.method,
        'route': match.view_name if match else 'unresolved',
    }


def resource_for(request):
    match = request.resolver_match
    if match:
        for value in match.kwargs.values():
            try:
                return UUID(str(value))
            except (ValueError, TypeError):
                continue
    return NO_RESOURCE
