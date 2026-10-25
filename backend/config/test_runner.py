from django.db import connections
from django.db.models.signals import post_migrate
from django.test.runner import DiscoverRunner


def initialize_test_singletons(sender=None, using="default", **kwargs):
    connection = connections[using]
    name = str(connection.settings_dict["NAME"])
    if connection.vendor != "postgresql" or not name.startswith("test_"):
        return

    from core.models import AuditHead, LocalCounter

    AuditHead.objects.using(using).get_or_create(pk=1)
    LocalCounter.objects.using(using).get_or_create(pk=1)


class VeridianTestRunner(DiscoverRunner):
    def run_suite(self, suite, **kwargs):
        uid = "veridian_postgresql_test_singletons"
        post_migrate.connect(
            initialize_test_singletons,
            dispatch_uid=uid,
            weak=False,
        )
        try:
            initialize_test_singletons()
            return super().run_suite(suite, **kwargs)
        finally:
            post_migrate.disconnect(dispatch_uid=uid)
