import re
import time
from django.core.exceptions import ValidationError
from django.contrib.auth import logout
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
class PasswordPolicy:
    def validate(self, password, user=None):
        if len(password) < 12 or not all(re.search(p, password) for p in [r'[A-Za-z]', r'\d', r'[^A-Za-z0-9]']):
            raise ValidationError(self.get_help_text())
    def get_help_text(self):
        return 'Use at least 12 characters including a letter, number, and special character.'
class IdleSessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result:
            last = request.session.get('last_activity', 0)
            if time.time() - last >= 1800:
                from .services import audit
                audit(result[0], 'auth.session_expired', result[0].id, {'reason': '30-minute inactivity limit reached.'})
                logout(request._request)
                raise AuthenticationFailed('Session expired after 30 minutes without user activity.')
        return result
