from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import Project, User
from .operational_visibility import operational_project_scope

class OperationalProjectSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.legal_name', read_only=True)
    class Meta:
        model = Project
        fields = ['id', 'code', 'customer', 'customer_name', 'location', 'sales_associate', 'state', 'created_at']
        read_only_fields = fields

class OperationalProjectPagination(PageNumberPagination):
    page_size = 50

class OperationalProjectViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OperationalProjectSerializer
    pagination_class = OperationalProjectPagination
    http_method_names = ['get', 'head', 'options']
    queryset = Project.objects.none()

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Project.objects.none()
        actor = User.objects.filter(pk=user.pk, is_active=True).first()
        if actor is None:
            return Project.objects.none()
        return operational_project_scope(actor).select_related('customer').order_by('-created_at', '-id')



    @action(
        detail=True,
        methods=["get"],
        url_path="installation-eligibility",
    )
    def installation_eligibility(self, request, pk=None):
        project = self.get_object()

        from .installation_readiness import installation_readiness

        result = installation_readiness(project)

        # Read-only evidence visibility; never installation authorization.
        from .models import (
            ExpeditedSigningAttempt,
            ExpeditedEnvelopeBinding,
            ExpeditedSigningObservation,
            ExpeditedSigningDocument,
        )

        from django.db import connections, router

        # Read-only schema check. Missing tables must not cause an HTTP 500
        # or be mistaken for verified expedited-service evidence.
        database_alias = router.db_for_read(ExpeditedSigningAttempt)
        connection = connections[database_alias]
        required_tables = {
            ExpeditedSigningAttempt._meta.db_table,
            ExpeditedEnvelopeBinding._meta.db_table,
            ExpeditedSigningObservation._meta.db_table,
            ExpeditedSigningDocument._meta.db_table,
        }
        with connection.cursor() as cursor:
            existing_tables = set(
                connection.introspection.table_names(cursor)
            )
        storage_available = required_tables.issubset(existing_tables)

        msr = project.current_approved
        attempted = False
        retained = False
        document_count = 0

        if storage_available and msr is not None and msr.status == "APPROVED":
            attempted = ExpeditedSigningAttempt.objects.filter(
                msr=msr
            ).exists()
            observations = ExpeditedSigningObservation.objects.filter(
                binding__attempt__msr=msr
            )
            retained = observations.exists()
            if retained:
                document_count = ExpeditedSigningDocument.objects.filter(
                    observation__in=observations
                ).count()

        result["expedited_service"] = {
            "status": (
                "SCHEMA_UNAVAILABLE"
                if not storage_available else
                "UNVERIFIED_DOCUMENTS_RETAINED"
                if retained else
                "ATTEMPT_RECORDED_UNVERIFIED"
                if attempted else
                "NO_RETAINED_EVIDENCE"
            ),
            "storage_available": storage_available,
            "attempt_recorded": attempted,
            "documents_retained": retained,
            "retained_document_count": document_count,
            "provider_authenticated": False,
            "signatures_verified": False,
            "distribution_verified": False,
            "expedited_authorized": False,
            "installation_authorized": False,
        }

        return Response({
            "project_id": project.id,
            **result,
        })

    @action(
        detail=True,
        methods=["get"],
        url_path="completion-signature-status",
    )
    def completion_signature_status(self, request, pk=None):
        project = self.get_object()
        return Response({
            "project_id": project.id,
            "status": "VERIFICATION_PENDING",
            "provider_verified": False,
            "installation_complete_qualified": False,
            "reason": "Trusted completion-signature verification is not yet available.",
        })

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

