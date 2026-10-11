"""Read-only, role-scoped project dashboard API."""

from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .dashboard_services import (
    DASHBOARD_STAGES,
    get_dashboard_projects,
    get_project_payment_breakdown,
)
from .operational_project_api import OperationalProjectSerializer


@never_cache
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_dashboard(request):
    grouped = get_dashboard_projects(request.user)

    stages = [
        {
            'key': key,
            'name': name,
            'count': len(grouped[key]),
            'projects': OperationalProjectSerializer(
                grouped[key],
                many=True,
            ).data,
        }
        for key, name in DASHBOARD_STAGES.items()
    ]

    for stage in stages:
        if stage['key'] != 'payment_received':
            continue

        projects_by_id = {
            str(project.id): project
            for project in grouped['payment_received']
        }

        for item in stage['projects']:
            project = projects_by_id[str(item['id'])]
            breakdown = get_project_payment_breakdown(project)

            item['payments'] = {
                'deposit': str(breakdown['DEPOSIT']),
                'final': str(breakdown['FINAL']),
                'full': str(breakdown['FULL']),
            }

    response = Response({'stages': stages})
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
