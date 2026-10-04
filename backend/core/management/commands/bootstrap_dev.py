import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password
from core.models import User, Role
class Command(BaseCommand):
    help = 'Create local development users; never available in production.'
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Development only.')
        password = os.environ.get('GECC_DEMO_PASSWORD', '')
        validate_password(password)
        for username, role, initials in [('sales', Role.SALES_ASSOCIATE, 'SA'), ('manager', Role.SALES_MANAGER, 'SM'), ('comptroller', Role.COMPTROLLER, 'CP')]:
            if not User.objects.filter(username=username).exists():
                User.objects.create_user(username=username, email=f'{username}@example.invalid', role=role, initials=initials, first_name='Demo', last_name=username.title(), password=password)
                self.stdout.write(f'Created {username}')
