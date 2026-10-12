import os
import subprocess
import sys
from pathlib import Path
from django.test import SimpleTestCase


class EnvironmentPolicyTests(SimpleTestCase):
    def test_environment_configuration(self):
        backend = Path(__file__).resolve().parent.parent
        cases = [
            ('legacy development', '1', None, True, 'development|True'),
            ('explicit development', '1', 'development', True, 'development|True'),
            ('staging', '0', 'staging', True, 'staging|False'),
            ('production', '0', 'production', True, 'production|False'),
            ('unauthorized development', '0', 'development', False, None),
            ('development in staging', '1', 'staging', False, None),
            ('development in production', '1', 'production', False, None),
            ('missing environment', '0', None, False, None),
            ('invalid environment', '0', 'testing', False, None),
            ('invalid legacy flag', 'yes', 'development', False, None),
        ]
        probe = (
            'import django; django.setup(); '
            'from django.conf import settings; '
            'print(settings.ENVIRONMENT + "|" + str(settings.DEBUG))'
        )

        for name, legacy, environment, should_start, expected in cases:
            with self.subTest(configuration=name):
                env = os.environ.copy()
                env['GECC_DEV'] = legacy
                env['DJANGO_SETTINGS_MODULE'] = 'config.settings'
                env['DJANGO_SECRET_KEY'] = 'temporary-test-secret-never-deploy'
                env['PGHOST'] = 'localhost'
                env['DJANGO_ALLOWED_HOSTS'] = 'localhost'
                if environment is None:
                    env.pop('VERIDIAN_ENVIRONMENT', None)
                else:
                    env['VERIDIAN_ENVIRONMENT'] = environment

                result = subprocess.run(
                    [sys.executable, '-c', probe],
                    cwd=backend,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if should_start:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), expected)
                else:
                    self.assertNotEqual(result.returncode, 0)

    def test_development_login_requires_development_environment(self):
        from django.test import Client, override_settings

        for environment in ('staging', 'production'):
            with self.subTest(environment=environment):
                with override_settings(ENVIRONMENT=environment, DEBUG=True, SECURE_SSL_REDIRECT=False):
                    response = Client().post(
                        '/api/dev-login/',
                        data='{}',
                        content_type='application/json',
                    )
                    self.assertEqual(response.status_code, 404)

    def test_development_auth_indicator_requires_development_environment(self):
        from unittest.mock import Mock
        from django.test import override_settings
        from rest_framework.test import APIRequestFactory, force_authenticate
        from core.api import me

        user = Mock()
        user.id = 'test-user'
        user.username = 'synthetic-user'
        user.role = 'SALES_ASSOCIATE'
        user.is_authenticated = True
        user.is_active = True

        for environment in ('staging', 'production'):
            with self.subTest(environment=environment):
                with override_settings(ENVIRONMENT=environment, DEBUG=True):
                    request = APIRequestFactory().get('/api/me/')
                    force_authenticate(request, user=user)
                    response = me(request)
                    self.assertEqual(response.status_code, 200)
                    self.assertFalse(response.data['development_auth'])