"""Default-disabled commercial status endpoint.

Operational project state and completion safeguards remain independent.
"""
import os

from django.conf import settings
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from rest_framework.exceptions import APIException, NotFound

from .sales_status_api_5002 import SalesStatusDetail


class SalesStatusSchemaUnavailable(APIException):
    status_code = 503
    default_detail = "Sales status storage is not ready."
    default_code = "sales_status_schema_unavailable"


class ControlledSalesStatusDetail(SalesStatusDetail):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)

        if (
            not settings.DEBUG
            or os.environ.get("GECC_SALES_STATUS_ENABLED") != "1"
        ):
            raise NotFound("Sales status endpoint is disabled.")

        tables = set(connection.introspection.table_names())
        required = {
            "core_project",
            "core_projectsalesstatuschange",
            "django_migrations",
        }
        if not required.issubset(tables):
            raise SalesStatusSchemaUnavailable()

        with connection.cursor() as cursor:
            columns = {
                col.name
                for col in connection.introspection.get_table_description(
                    cursor, "core_project"
                )
            }
        if "sales_status" not in columns:
            raise SalesStatusSchemaUnavailable()

        applied = MigrationRecorder.Migration.objects.using(
            connection.alias
        ).filter(
            app="core",
            name="0088_sales_status_audit_guard_5003",
        ).exists()
        if not applied:
            raise SalesStatusSchemaUnavailable()
