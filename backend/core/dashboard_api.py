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

    # Only annotate projects already returned by role-scoped visibility.
    from .dashboard_guidance import project_guidance

    for stage in stages:
        scoped = {
            str(project.id): project
            for project in grouped[stage['key']]
        }
        for item in stage['projects']:
            item['guidance'] = project_guidance(
                scoped[str(item['id'])].state, stage['key']
            )

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

    # Reuse existing role-scoped visibility; do not infer new milestones.
    from .dashboard_attention import get_attention_projects, attention_hint
    waiting = get_attention_projects(request.user)
    attention = OperationalProjectSerializer(waiting, many=True).data
    for project in attention:
        project['guidance'] = attention_hint(project['state'])

    # The stage lists and attention list have already been restricted
    # by the existing role-scoped dashboard services.
    from .dashboard_workflow_evidence_4257 import describe_workflow_evidence

    visible = {}
    for stage_key, scoped_projects in grouped.items():
        for scoped_project in scoped_projects:
            visible[str(scoped_project.pk)] = scoped_project
    for scoped_project in waiting:
        visible[str(scoped_project.pk)] = scoped_project

    evidence_by_id = {
        project_id: describe_workflow_evidence(scoped_project)
        for project_id, scoped_project in visible.items()
    }

    for stage in stages:
        for item in stage['projects']:
            item['workflow_evidence'] = evidence_by_id[str(item['id'])]

    for item in attention:
        item['workflow_evidence'] = evidence_by_id[str(item['id'])]
    response = Response({'stages': stages, 'needs_attention': attention})
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
