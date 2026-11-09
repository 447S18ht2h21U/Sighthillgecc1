"""Authenticated, Comptroller-only corporate financial reporting API.

Routes are deliberately not registered until API security tests pass.
Report calculations, approvals, and audit evidence remain service-owned.
"""

from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache

from rest_framework import serializers
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .corporate_reporting_services import (
    create_corporate_financial_report,
)
from .financial_report_services import approve_financial_report
from .financial_reporting_authorization import (
    require_financial_reporting_role,
)
from .models import FinancialReport, Role


class FinancialReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialReport
        fields = [
            "id",
            "created_at",
            "kind",
            "period_start",
            "period_end",
            "report_snapshot",
            "status",
            "created_by",
            "approved_by",
            "approved_at",
        ]
        read_only_fields = fields


class FinancialReportCreateInput(serializers.Serializer):
    report_kind = serializers.ChoiceField(
        choices=[
            FinancialReport.Kind.INCOME_STATEMENT,
            FinancialReport.Kind.BALANCE_SHEET,
            FinancialReport.Kind.CASH_FLOW,
        ]
    )
    frequency = serializers.ChoiceField(
        choices=["MONTHLY", "QUARTERLY", "ANNUAL"]
    )
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    period_number = serializers.IntegerField(
        min_value=1,
        max_value=12,
        required=False,
        allow_null=True,
    )

    def to_internal_value(self, data):
        if not hasattr(data, "keys"):
            raise serializers.ValidationError(
                {"detail": "Expected a JSON object."}
            )

        unexpected = sorted(
            set(data.keys()) - set(self.fields.keys())
        )

        if unexpected:
            raise serializers.ValidationError({
                "unexpected_fields": unexpected,
            })

        return super().to_internal_value(data)


def _authorized_actor(request, operation="read"):
    from django.conf import settings as financial_settings
    from rest_framework.exceptions import PermissionDenied

    ceo_policy = (
        getattr(
            financial_settings,
            "VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED",
            False,
        ) is True
    )

    if not ceo_policy:
        return require_financial_reporting_role(
            request.user, Role.COMPTROLLER
        )

    if operation == "create":
        return require_financial_reporting_role(
            request.user, Role.COMPTROLLER
        )

    if operation == "approve":
        return require_financial_reporting_role(
            request.user, Role.CEO
        )

    if operation == "read":
        if getattr(request.user, "role", None) == Role.CEO:
            return require_financial_reporting_role(
                request.user, Role.CEO
            )
        return require_financial_reporting_role(
            request.user, Role.COMPTROLLER
        )

    raise PermissionDenied("Unsupported financial report operation.")


def _no_store(response):
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@never_cache
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def financial_reports(request):
    actor = _authorized_actor(
        request,
        operation="create" if request.method == "POST" else "read",
    )

    if request.method == "GET":
        records = (
            FinancialReport.objects
            .select_related("created_by", "approved_by")
            .order_by("-period_end", "kind", "-created_at")
        )
        return _no_store(
            Response({
                "results": FinancialReportSerializer(
                    records[:100],
                    many=True,
                ).data,
            })
        )

    data = FinancialReportCreateInput(data=request.data)
    data.is_valid(raise_exception=True)

    values = data.validated_data

    report = create_corporate_financial_report(
        actor=actor,
        report_kind=values["report_kind"],
        frequency=values["frequency"],
        year=values["year"],
        period_number=values.get("period_number"),
    )

    return _no_store(
        Response(
            FinancialReportSerializer(report).data,
            status=201,
        )
    )


@never_cache
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def financial_report_detail(request, report_id):
    _authorized_actor(request)

    report = get_object_or_404(
        FinancialReport,
        pk=report_id,
    )

    return _no_store(
        Response(FinancialReportSerializer(report).data)
    )


@never_cache
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def financial_report_approve(request, report_id):
    actor = _authorized_actor(request, operation="approve")

    report = approve_financial_report(
        actor=actor,
        report_id=report_id,
    )

    return _no_store(
        Response(FinancialReportSerializer(report).data)
    )
