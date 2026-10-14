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

        return Response({
            "project_id": project.id,
            **result,
        })

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

