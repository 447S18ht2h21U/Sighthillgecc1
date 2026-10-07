from django.db import transaction
from django.http import JsonResponse
from .audit_context import context_for, request_context, resource_for
from .services import audit


class AccessAuditMiddleware:
    """Record one outcome per protected read/denial, outside view rollback.

    Authentication events are recorded separately at their source. Ordinary
    activity/CSRF requests are excluded; auditing never updates last_activity.
    """
    excluded = {'/api/csrf/', '/api/me/', '/api/activity/', '/api/dev-login/',
                '/api/logout/', '/api/docusign/callback/'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Django resolves the URL after middleware starts. Resolve a safe route
        # identifier here so mutation events also receive request context.
        from django.urls import resolve, Resolver404
        try:
            request.resolver_match = resolve(request.path_info)
        except Resolver404:
            pass
        token = request_context.set(context_for(request))
        try:
            response = self.get_response(request)
            if not request.path_info.startswith('/api/') or not request.resolver_match:
                return response
            actor = request.user if request.user.is_authenticated else None
            protected = request.path_info not in self.excluded
            action = None
            if response.status_code in {401, 403}:
                action = 'access.denied'
            elif protected and response.status_code == 404:
                action = 'access.unavailable'
            elif protected and response.status_code in {400, 405, 409, 422}:
                action = 'access.failed'
            elif protected and request.method == 'GET' and 200 <= response.status_code < 300:
                action = 'access.download' if response.get('Content-Type', '').startswith('application/pdf') else 'access.read'
            if action:
                try:
                    with transaction.atomic():
                        audit(actor, action, resource_for(request), {'status': response.status_code})
                except Exception as error:
                    import logging
                    logging.getLogger(__name__).error('Access audit failed (%s).', type(error).__name__)
                    # Do not release a protected read if its evidence cannot be
                    # retained. Discard the original response and its contents.
                    response = JsonResponse({'detail': 'Audit recording is unavailable. Please try again.'}, status=503)
                    response['Cache-Control'] = 'private, no-store'
            return response
        finally:
            request_context.reset(token)
